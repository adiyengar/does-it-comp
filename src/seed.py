"""Seed the evidence table from the committed snapshot if the DB is empty."""
import json
from pathlib import Path
from .db import get_conn
from .models import Evidence
from .retrieve import save_evidence

SNAPSHOT = Path(__file__).parent.parent / "data" / "raw" / "teams_snapshot.json"


def seed_if_empty() -> int:
    """Load snapshot into DB if evidence table is empty. Returns records loaded."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    if count > 0:
        return 0
    if not SNAPSHOT.exists():
        return 0
    records = json.loads(SNAPSHOT.read_text())
    for r in records:
        ev = Evidence(
            id=r["id"],
            part_a_pid=r["part_a_pid"],
            part_b_pid=r["part_b_pid"],
            tier=r["tier"],
            supports=bool(r["supports"]) if r["supports"] is not None else None,
            conditions=r["conditions"],
            source_name=r["source_name"],
            source_url=r["source_url"],
            retrieved_at=r["retrieved_at"],
            raw_text=r.get("raw_text", ""),
        )
        save_evidence(ev)
    return len(records)
