import json
from .models import Answer, Escalation, Question
from .db import get_conn
from . import capture, classify, draft as draft_mod, escalate, resolve, retrieve
from .gate import decide


def _save_question(q: Question) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO questions
               (id, raw_text, part_a_raw, part_b_raw, part_a_pid, part_b_pid,
                part_a_confidence, part_b_confidence, question_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                q.id, q.raw_text, q.part_a_raw, q.part_b_raw,
                q.part_a_pid, q.part_b_pid,
                q.part_a_confidence, q.part_b_confidence,
                q.question_type, q.created_at,
            ),
        )


def _save_answer(a: Answer) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO answers
               (id, question_id, shape, text, evidence_ids, gate_decision, risk_flags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                a.id, a.question_id, a.shape, a.text,
                json.dumps(a.evidence_ids), a.gate_decision,
                json.dumps(a.risk_flags), a.created_at,
            ),
        )


def run(raw_question: str, part_a_raw: str, part_b_raw: str) -> dict:
    """
    Orchestrates the full pipeline. Returns a result dict with keys:
      source: "cache" | "auto" | "escalation"
      shape, text, evidence, risk_flags, question_id, answer_id
      (escalation only) escalation_id, notification
      (cache only) verified_by, verified_at
    """
    question_type = classify.classify(raw_question)
    part_a_pid, part_a_conf = resolve.resolve(part_a_raw)
    part_b_pid, part_b_conf = resolve.resolve(part_b_raw)

    # Effective keys: resolved PID when available, raw text otherwise
    eff_a = part_a_pid or part_a_raw.strip()
    eff_b = part_b_pid or part_b_raw.strip()

    q = Question(
        raw_text=raw_question,
        part_a_raw=part_a_raw,
        part_b_raw=part_b_raw,
        question_type=question_type,
        part_a_pid=part_a_pid,
        part_b_pid=part_b_pid,
        part_a_confidence=part_a_conf,
        part_b_confidence=part_b_conf,
    )
    _save_question(q)

    # Canonical cache hit — instant answer from prior expert verification
    if eff_a and eff_b:
        cached = capture.get_canonical(eff_a, eff_b, question_type)
        if cached:
            return {
                "source": "cache",
                "shape": "confirmed",
                "text": cached["answer_text"],
                "verified_by": cached["verified_by"],
                "verified_at": cached["verified_at"],
                "evidence_ids": cached["evidence_ids"],
                "question_id": q.id,
            }

    evidence = retrieve.get_evidence(part_a_pid, part_b_pid) if part_a_pid and part_b_pid else []
    alts = retrieve.find_alternatives(part_b_pid, [part_a_pid]) if part_b_pid else []

    d = draft_mod.draft(q, evidence, alts)
    decision, flags = decide(q, evidence, d)

    a = Answer(
        question_id=q.id,
        shape=d.shape,
        text=d.text,
        evidence_ids=d.evidence_ids,
        gate_decision=decision,
        risk_flags=flags,
    )
    _save_answer(a)

    ev_dicts = [
        {
            "id": e.id, "tier": e.tier, "source": e.source_name,
            "url": e.source_url, "supports": e.supports, "conditions": e.conditions,
        }
        for e in evidence
    ]

    if decision == "AUTO_ANSWER":
        return {
            "source": "auto",
            "shape": d.shape,
            "text": d.text,
            "evidence": ev_dicts,
            "risk_flags": flags,
            "question_id": q.id,
            "answer_id": a.id,
        }

    esc = Escalation(
        question_id=q.id,
        answer_id=a.id,
        draft_text=d.text,
        evidence_summary=[
            {
                "tier": e.tier, "source": e.source_name, "url": e.source_url,
                "retrieved_at": e.retrieved_at, "conditions": e.conditions,
            }
            for e in evidence
        ],
        why_escalated="; ".join(flags) if flags else "insufficient evidence",
    )
    escalate.save_escalation(esc)

    return {
        "source": "escalation",
        "escalation_id": esc.id,
        "notification": escalate.build_notification(q, evidence, a, esc),
        "shape": d.shape,
        "text": d.text,
        "evidence": ev_dicts,
        "risk_flags": flags,
        "question_id": q.id,
        "answer_id": a.id,
    }
