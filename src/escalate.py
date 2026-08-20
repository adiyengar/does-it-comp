import json
from .db import get_conn
from .models import Answer, Escalation, Evidence, Question


def _tier_line(e: dict) -> str:
    cond = f"  [{', '.join(e['conditions'])}]" if e.get("conditions") else ""
    return f"  {e['tier']}  {e['source']}{cond}  (retrieved {e['retrieved_at']})"


def build_notification(
    question: Question,
    evidence: list[Evidence],
    answer: Answer,
    esc: Escalation,
) -> str:
    ev_lines = "\n".join(
        f"  {e.tier}  {e.source_name}"
        + (f"  [{', '.join(e.conditions)}]" if e.conditions else "")
        + f"  (retrieved {e.retrieved_at})"
        for e in evidence
    ) or "  (no evidence found)"

    return (
        f"COMPATIBILITY QUESTION ROUTED FOR EXPERT REVIEW\n"
        f"{'═' * 50}\n\n"
        f"Question:      {question.raw_text}\n"
        f"Resolved as:   {question.part_a_pid or '(unresolved)'} "
        f"(conf {question.part_a_confidence:.2f}) · "
        f"{question.part_b_pid or '(unresolved)'} "
        f"(conf {question.part_b_confidence:.2f})\n\n"
        f"Draft answer:\n"
        f"  {answer.text}\n\n"
        f"Evidence:\n{ev_lines}\n\n"
        f"WHY THIS CAME TO YOU:\n"
        f"  {esc.why_escalated}\n\n"
        f"Record ID: {esc.id}\n"
    )


def save_escalation(esc: Escalation) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO escalations
               (id, question_id, answer_id, draft_text, evidence_summary,
                why_escalated, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                esc.id, esc.question_id, esc.answer_id, esc.draft_text,
                json.dumps(esc.evidence_summary),
                esc.why_escalated, esc.created_at,
            ),
        )


def get_escalation(esc_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM escalations WHERE id = ?", (esc_id,)
        ).fetchone()
    return dict(row) if row else None
