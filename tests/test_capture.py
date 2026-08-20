"""Tests for capture.py — reason codes write correct records and canonical cache works."""
import pytest
from datetime import datetime
from src.db import init_db, get_conn
from src.models import Answer, CanonicalAnswer, Escalation, ExpertResponse, Question
from src import capture, escalate


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Redirect DB to a temp file so tests are isolated."""
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_escalation(esc_id: str = "esc-001") -> None:
    q = Question(
        id="q-001", raw_text="Can A work with B?",
        part_a_raw="A", part_b_raw="B", question_type="compatibility",
        part_a_pid="PART-A", part_b_pid="PART-B",
        part_a_confidence=0.5, part_b_confidence=0.5,
    )
    a = Answer(
        id="ans-001", question_id="q-001", shape="escalated",
        text="Uncertain.", evidence_ids=[], gate_decision="ESCALATE", risk_flags=["test"],
    )
    esc = Escalation(
        id=esc_id, question_id="q-001", answer_id="ans-001",
        draft_text="Uncertain.", evidence_summary=[], why_escalated="no T1 evidence",
    )
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (q.id, q.raw_text, q.part_a_raw, q.part_b_raw,
             q.part_a_pid, q.part_b_pid, q.part_a_confidence,
             q.part_b_confidence, q.question_type, q.created_at),
        )
        conn.execute(
            "INSERT INTO answers VALUES (?,?,?,?,?,?,?,?)",
            (a.id, a.question_id, a.shape, a.text,
             "[]", a.gate_decision, "[]", a.created_at),
        )
    escalate.save_escalation(esc)


def _response(**overrides) -> ExpertResponse:
    defaults = dict(
        escalation_id="esc-001",
        answer_final="Yes, compatible with adapter X.",
        verdict="edited",
        reason_code="conditions_incomplete",
        sources_used=["http://example.com/doc"],
        tier_assigned="T1",
        conditions=["requires adapter X"],
        should_have_auto_answered=False,
        time_to_respond=45.2,
        reviewer_id="expert@example.com",
    )
    defaults.update(overrides)
    return ExpertResponse(**defaults)


# ── Expert response writes correct records ────────────────────────────────────

def test_save_expert_response_persists_record():
    _seed_escalation()
    capture.save_expert_response(_response())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM expert_responses WHERE escalation_id = 'esc-001'"
        ).fetchone()
    assert row is not None
    assert row["verdict"] == "edited"
    assert row["reason_code"] == "conditions_incomplete"


def test_save_expert_response_marks_escalation_resolved():
    _seed_escalation()
    capture.save_expert_response(_response(verdict="approved"))
    with get_conn() as conn:
        esc = conn.execute("SELECT * FROM escalations WHERE id = 'esc-001'").fetchone()
    assert esc["verdict"] == "approved"
    assert esc["resolved_at"] is not None


@pytest.mark.parametrize("code", [
    "wrong_sku_resolved",
    "source_missing",
    "source_misread",
    "source_wrong",
    "question_misclassified",
    "conditions_incomplete",
    "answer_correct_but_escalated",
])
def test_all_reason_codes_persist(code):
    _seed_escalation(esc_id=f"esc-{code}")
    capture.save_expert_response(_response(escalation_id=f"esc-{code}", reason_code=code))
    with get_conn() as conn:
        row = conn.execute(
            "SELECT reason_code FROM expert_responses WHERE escalation_id = ?",
            (f"esc-{code}",),
        ).fetchone()
    assert row["reason_code"] == code


# ── Canonical answer cache ────────────────────────────────────────────────────

def test_save_canonical_creates_cache_entry():
    ca = CanonicalAnswer(
        part_a_pid="PART-A", part_b_pid="PART-B", question_type="compatibility",
        answer_text="Yes, compatible [ev-001].",
        evidence_ids=["ev-001"],
        verified_by="expert@example.com",
        verified_at=datetime.utcnow().isoformat(),
    )
    capture.save_canonical(ca)
    result = capture.get_canonical("PART-A", "PART-B", "compatibility")
    assert result is not None
    assert result["answer_text"] == "Yes, compatible [ev-001]."
    assert result["evidence_ids"] == ["ev-001"]


def test_get_canonical_finds_reversed_pair():
    ca = CanonicalAnswer(
        part_a_pid="PART-A", part_b_pid="PART-B", question_type="compatibility",
        answer_text="Yes [ev-001].", evidence_ids=["ev-001"],
        verified_by="expert@example.com", verified_at=datetime.utcnow().isoformat(),
    )
    capture.save_canonical(ca)
    result = capture.get_canonical("PART-B", "PART-A", "compatibility")
    assert result is not None


def test_get_canonical_returns_none_for_unknown_pair():
    result = capture.get_canonical("UNKNOWN-A", "UNKNOWN-B", "compatibility")
    assert result is None


def test_canonical_upsert_replaces_on_same_pair():
    ts = datetime.utcnow().isoformat()
    for text in ["Version 1.", "Version 2."]:
        ca = CanonicalAnswer(
            part_a_pid="PART-A", part_b_pid="PART-B", question_type="compatibility",
            answer_text=text, evidence_ids=[], verified_by="expert@example.com", verified_at=ts,
        )
        capture.save_canonical(ca)
    result = capture.get_canonical("PART-A", "PART-B", "compatibility")
    assert result["answer_text"] == "Version 2."
