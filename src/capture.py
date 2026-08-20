import json
from datetime import datetime
from .db import get_conn
from .models import CanonicalAnswer, ExpertResponse


def save_expert_response(resp: ExpertResponse) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO expert_responses
               (id, escalation_id, answer_final, verdict, reason_code, sources_used,
                tier_assigned, conditions, should_have_auto_answered,
                time_to_respond, reviewer_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                resp.id, resp.escalation_id, resp.answer_final, resp.verdict,
                resp.reason_code, json.dumps(resp.sources_used),
                resp.tier_assigned, json.dumps(resp.conditions),
                int(resp.should_have_auto_answered),
                resp.time_to_respond, resp.reviewer_id, resp.created_at,
            ),
        )
        conn.execute(
            "UPDATE escalations SET resolved_at = ?, verdict = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), resp.verdict, resp.escalation_id),
        )


def save_canonical(ca: CanonicalAnswer) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO canonical_answers
               (id, part_a_pid, part_b_pid, question_type, answer_text,
                evidence_ids, verified_by, verified_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ca.id, ca.part_a_pid, ca.part_b_pid, ca.question_type,
                ca.answer_text, json.dumps(ca.evidence_ids),
                ca.verified_by, ca.verified_at, ca.expires_at,
            ),
        )


def get_canonical(part_a_pid: str, part_b_pid: str, question_type: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM canonical_answers
               WHERE question_type = ?
                 AND ((part_a_pid = ? AND part_b_pid = ?)
                   OR (part_a_pid = ? AND part_b_pid = ?))
               LIMIT 1""",
            (question_type, part_a_pid, part_b_pid, part_b_pid, part_a_pid),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["evidence_ids"] = json.loads(result["evidence_ids"])
    return result
