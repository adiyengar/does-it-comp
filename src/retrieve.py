import json
from .db import get_conn
from .models import Evidence


def _row_to_evidence(row) -> Evidence:
    return Evidence(
        id=row["id"],
        part_a_pid=row["part_a_pid"],
        part_b_pid=row["part_b_pid"],
        tier=row["tier"],
        supports=bool(row["supports"]) if row["supports"] is not None else None,
        conditions=json.loads(row["conditions"]),
        source_name=row["source_name"],
        source_url=row["source_url"],
        retrieved_at=row["retrieved_at"],
        raw_text=row["raw_text"] or "",
    )


def get_evidence(part_a_pid: str, part_b_pid: str) -> list[Evidence]:
    """Return all evidence for this part pair (either order), best tier first."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM evidence
               WHERE (part_a_pid = ? AND part_b_pid = ?)
                  OR (part_a_pid = ? AND part_b_pid = ?)
               ORDER BY tier ASC""",
            (part_a_pid, part_b_pid, part_b_pid, part_a_pid),
        ).fetchall()
    return [_row_to_evidence(r) for r in rows]


def find_alternatives(pid: str, exclude: list[str] | None = None) -> list[str]:
    """Return up to 5 PIDs that have T1 'supported' evidence with pid."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT
                 CASE WHEN part_a_pid = ? THEN part_b_pid ELSE part_a_pid END AS alt
               FROM evidence
               WHERE (part_a_pid = ? OR part_b_pid = ?)
                 AND tier = 'T1' AND supports = 1""",
            (pid, pid, pid),
        ).fetchall()
    alts = [r[0] for r in rows]
    if exclude:
        alts = [a for a in alts if a not in exclude]
    return alts[:5]


def save_evidence(ev: Evidence) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO evidence
               (id, part_a_pid, part_b_pid, tier, supports, conditions,
                source_name, source_url, retrieved_at, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ev.id, ev.part_a_pid, ev.part_b_pid, ev.tier,
                int(ev.supports) if ev.supports is not None else None,
                json.dumps(ev.conditions),
                ev.source_name, ev.source_url, ev.retrieved_at, ev.raw_text,
            ),
        )
