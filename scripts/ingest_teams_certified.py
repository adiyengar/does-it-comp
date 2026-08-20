#!/usr/bin/env python3
"""
Ingest Microsoft Teams Rooms certified hardware from learn.microsoft.com.
Each certified device is T1 evidence — binary, authoritative.
"""
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import init_db
from src.models import Evidence
from src.retrieve import save_evidence

PAGES = [
    (
        "https://learn.microsoft.com/en-us/microsoftteams/rooms/certified-hardware",
        "Teams Rooms Certified Hardware",
    ),
    (
        "https://learn.microsoft.com/en-us/microsoftteams/devices/teams-panels-certified-hardware",
        "Teams Panels Certified Hardware",
    ),
]

PLATFORM_PID = "Microsoft-Teams-Rooms"
HEADERS = {
    "User-Agent": (
        "compatibility-agent-poc/0.1 "
        "(educational PoC; contact adi@u.northwestern.edu)"
    )
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"  # enforce UTF-8; requests sometimes guesses wrong
    return BeautifulSoup(resp.text, "lxml")


def extract_devices(soup: BeautifulSoup, source_name: str, source_url: str) -> list[Evidence]:
    """Each device in a certified hardware table is T1-supported with Teams Rooms."""
    records: list[Evidence] = []
    retrieved = datetime.utcnow().isoformat()

    for table in soup.find_all("table"):
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            device = re.sub(r"\s+", " ", cells[0].get_text(strip=True))
            if len(device) < 3:
                continue
            records.append(
                Evidence(
                    part_a_pid=device,
                    part_b_pid=PLATFORM_PID,
                    tier="T1",
                    supports=True,
                    conditions=[],
                    source_name=source_name,
                    source_url=source_url,
                    retrieved_at=retrieved,
                    raw_text=f"'{device}' certified on {source_name}",
                )
            )
    return records


def main() -> None:
    init_db()
    total = 0
    for url, name in PAGES:
        print(f"Fetching {name} ...")
        try:
            soup = fetch_page(url)
            records = extract_devices(soup, name, url)
            for ev in records:
                save_evidence(ev)
            print(f"  Saved {len(records)} records")
            total += len(records)
            time.sleep(2)
        except Exception as exc:
            print(f"  ERROR: {exc}")
    print(f"Done. Total records saved: {total}")


if __name__ == "__main__":
    main()
