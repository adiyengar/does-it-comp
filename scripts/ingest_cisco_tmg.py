#!/usr/bin/env python3
"""
Ingest Cisco TMG compatibility data.
Strategy 1: pytmg (unofficial client — verify before depending on it).
Strategy 2: Excel export committed to data/raw/.

Download the TMG export from https://tmgmatrix.cisco.com and save it to data/raw/
if pytmg is unavailable or broken.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import init_db
from src.models import Evidence
from src.retrieve import save_evidence

SOURCE_NAME = "Cisco TMG Compatibility Matrix"
SOURCE_URL = "https://tmgmatrix.cisco.com"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _try_pytmg() -> list[Evidence]:
    try:
        import pytmg  # noqa: F401
    except ImportError:
        print("  pytmg not installed — run: uv pip install pytmg")
        return []

    retrieved = datetime.utcnow().isoformat()
    records: list[Evidence] = []
    try:
        # pytmg 0.0.6 uses TMG.TMG().search_device(pid) — a per-device search,
        # not a bulk export. The Cisco public API also returns 500 as of 2026-08.
        # This path will not yield records; fall through to Excel.
        from pytmg import TMG as TMGModule
        client = TMGModule.TMG()
        results = client.search_device("test")  # probe the API
        # If the probe succeeds, results is a list of TMGResult objects
        for row in results or []:
            pid_a = str(getattr(row, "sfp_pid", "") or "").strip()
            pid_b = str(getattr(row, "platform_pid", "") or "").strip()
            if not pid_a or not pid_b:
                continue
            records.append(
                Evidence(
                    part_a_pid=pid_a,
                    part_b_pid=pid_b,
                    tier="T1",
                    supports=True,
                    conditions=[],
                    source_name=SOURCE_NAME,
                    source_url=SOURCE_URL,
                    retrieved_at=retrieved,
                    raw_text=str(row)[:300],
                )
            )
            if len(records) % 500 == 0:
                print(f"  ... {len(records)} records")
    except Exception as exc:
        print(f"  pytmg failed: {exc}")
        return []
    return records


def _try_excel() -> list[Evidence]:
    try:
        import openpyxl
    except ImportError:
        print("  openpyxl not installed — run: uv pip install openpyxl")
        return []

    excels = sorted(RAW_DIR.glob("*.xlsx")) + sorted(RAW_DIR.glob("*.xls"))
    if not excels:
        print(f"  No Excel files in {RAW_DIR}")
        return []

    retrieved = datetime.utcnow().isoformat()
    records: list[Evidence] = []
    for path in excels:
        print(f"  Reading {path.name} ...")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for sheet in wb.worksheets:
            all_rows = list(sheet.iter_rows(values_only=True))
            if not all_rows:
                continue
            headers = [str(h).lower().strip() if h else "" for h in all_rows[0]]
            for raw_row in all_rows[1:]:
                if not any(raw_row):
                    continue
                d = {headers[i]: raw_row[i] for i in range(min(len(headers), len(raw_row)))}
                pid_a = str(d.get("sfp pid") or d.get("transceiver") or d.get("part") or "").strip()
                pid_b = str(d.get("platform") or d.get("switch") or d.get("device") or "").strip()
                if not pid_a or not pid_b or pid_a == "None" or pid_b == "None":
                    continue
                records.append(
                    Evidence(
                        part_a_pid=pid_a,
                        part_b_pid=pid_b,
                        tier="T1",
                        supports=True,
                        conditions=[],
                        source_name=SOURCE_NAME,
                        source_url=SOURCE_URL,
                        retrieved_at=retrieved,
                        raw_text=str(d)[:300],
                    )
                )
    return records


def main() -> None:
    init_db()
    print("Trying pytmg ...")
    records = _try_pytmg()
    if not records:
        print("Falling back to Excel files in data/raw/ ...")
        records = _try_excel()
    if not records:
        print(
            "\nNo Cisco data ingested.\n"
            "Status: pytmg 0.0.6 is installed but the Cisco public API "
            "is returning 500 errors (verified 2026-08).\n\n"
            "To get Cisco data:\n"
            f"  1. Visit {SOURCE_URL}\n"
            f"  2. Export to Excel (button in top-right)\n"
            f"  3. Save the file to data/raw/\n"
            f"  4. Re-run this script\n"
        )
        return
    print(f"Saving {len(records)} records ...")
    for ev in records:
        save_evidence(ev)
    print(f"Done. {len(records)} Cisco TMG records saved.")


if __name__ == "__main__":
    main()
