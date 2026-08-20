"""Deterministic risk gate. No LLM calls. Pure function — unit tested in tests/test_gate.py."""
from datetime import datetime
from .models import Draft, Evidence, Question
from .classify import HIGH_LIABILITY

SKU_CONFIDENCE_THRESHOLD = 0.85
STALENESS_DAYS = 365


def decide(
    question: Question,
    evidence: list[Evidence],
    draft: Draft,
) -> tuple[str, list[str]]:
    """
    Return (AUTO_ANSWER | ESCALATE, list_of_reason_strings).
    Any non-empty reason list means ESCALATE.
    Only T1 evidence with no flags leads to AUTO_ANSWER.
    """
    flags: list[str] = []

    # 1. SKU resolution confidence below threshold
    if question.part_a_confidence < SKU_CONFIDENCE_THRESHOLD:
        flags.append(
            f"part_a_confidence {question.part_a_confidence:.2f} below threshold {SKU_CONFIDENCE_THRESHOLD}"
        )
    if question.part_b_confidence < SKU_CONFIDENCE_THRESHOLD:
        flags.append(
            f"part_b_confidence {question.part_b_confidence:.2f} below threshold {SKU_CONFIDENCE_THRESHOLD}"
        )

    # 2. High-liability question type
    if question.question_type in HIGH_LIABILITY:
        flags.append(f"question_type '{question.question_type}' is high-liability — always routes to expert")

    # 3. No T1 evidence present
    if not any(e.tier == "T1" for e in evidence):
        flags.append("no T1 evidence present (only T1 vendor statements auto-answer)")

    # 4. Conflicting evidence
    support_vals = {e.supports for e in evidence if e.supports is not None}
    if True in support_vals and False in support_vals:
        flags.append("evidence sources conflict: some say supported, some say not supported")

    # 5. Draft contains no linked evidence IDs
    if not draft.evidence_ids:
        flags.append("draft contains no linked evidence — cannot verify claims")

    # 6. Stale evidence
    now = datetime.utcnow()
    for e in evidence:
        try:
            age = (now - datetime.fromisoformat(e.retrieved_at)).days
            if age > STALENESS_DAYS:
                flags.append(f"evidence from '{e.source_name}' is stale ({e.retrieved_at}, {age} days old)")
        except ValueError:
            pass

    return ("ESCALATE" if flags else "AUTO_ANSWER"), flags
