"""
Gate tests — one test per escalation trigger, plus proof that T1-only path auto-answers
and T3-only path never does.
"""
import pytest
from datetime import datetime, timedelta
from src.models import Draft, Evidence, Question
from src.gate import decide, SKU_CONFIDENCE_THRESHOLD, STALENESS_DAYS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _question(**overrides) -> Question:
    defaults = dict(
        raw_text="Can A connect to B?",
        part_a_raw="Part A",
        part_b_raw="Part B",
        question_type="compatibility",
        part_a_pid="PART-A",
        part_b_pid="PART-B",
        part_a_confidence=0.95,
        part_b_confidence=0.95,
    )
    defaults.update(overrides)
    return Question(**defaults)


def _t1_ev(supports: bool = True) -> Evidence:
    return Evidence(
        part_a_pid="PART-A", part_b_pid="PART-B", tier="T1",
        supports=supports, source_name="Test", source_url="http://test.example",
        retrieved_at=datetime.utcnow().isoformat(),
    )


def _draft(evidence_ids: list[str] | None = None) -> Draft:
    return Draft(
        shape="confirmed",
        text="Yes, compatible [ev-001].",
        evidence_ids=evidence_ids if evidence_ids is not None else ["ev-001"],
    )


# ── Auto-answer path (the happy path) ────────────────────────────────────────

def test_t1_only_auto_answers():
    decision, flags = decide(_question(), [_t1_ev()], _draft())
    assert decision == "AUTO_ANSWER"
    assert flags == []


# ── Trigger 1: SKU confidence ─────────────────────────────────────────────────

def test_low_part_a_confidence_escalates():
    q = _question(part_a_confidence=SKU_CONFIDENCE_THRESHOLD - 0.01)
    decision, flags = decide(q, [_t1_ev()], _draft())
    assert decision == "ESCALATE"
    assert any("part_a_confidence" in f for f in flags)


def test_low_part_b_confidence_escalates():
    q = _question(part_b_confidence=SKU_CONFIDENCE_THRESHOLD - 0.01)
    decision, flags = decide(q, [_t1_ev()], _draft())
    assert decision == "ESCALATE"
    assert any("part_b_confidence" in f for f in flags)


def test_exactly_at_threshold_does_not_escalate():
    q = _question(part_a_confidence=SKU_CONFIDENCE_THRESHOLD, part_b_confidence=SKU_CONFIDENCE_THRESHOLD)
    decision, _ = decide(q, [_t1_ev()], _draft())
    assert decision == "AUTO_ANSWER"


# ── Trigger 2: High-liability question type ───────────────────────────────────

@pytest.mark.parametrize("qtype", ["performance_at_scale", "licensing", "warranty", "other"])
def test_high_liability_type_escalates(qtype):
    q = _question(question_type=qtype)
    decision, flags = decide(q, [_t1_ev()], _draft())
    assert decision == "ESCALATE"
    assert any("high-liability" in f for f in flags)


def test_compatibility_type_does_not_trigger_liability_flag():
    q = _question(question_type="compatibility")
    _, flags = decide(q, [_t1_ev()], _draft())
    assert not any("high-liability" in f for f in flags)


# ── Trigger 3: No T1 evidence ─────────────────────────────────────────────────

def test_no_evidence_escalates():
    decision, flags = decide(_question(), [], _draft(evidence_ids=[]))
    assert decision == "ESCALATE"
    assert any("T1" in f for f in flags)


def test_t2_only_escalates():
    ev = [Evidence(
        part_a_pid="PART-A", part_b_pid="PART-B", tier="T2",
        supports=True, source_name="Test", source_url="http://test.example",
        retrieved_at=datetime.utcnow().isoformat(),
    )]
    decision, flags = decide(_question(), ev, _draft())
    assert decision == "ESCALATE"
    assert any("T1" in f for f in flags)


def test_t3_only_never_auto_answers():
    ev = [Evidence(
        part_a_pid="PART-A", part_b_pid="PART-B", tier="T3",
        supports=True, source_name="Test", source_url="http://test.example",
        retrieved_at=datetime.utcnow().isoformat(),
    )]
    decision, _ = decide(_question(), ev, _draft())
    assert decision == "ESCALATE"


# ── Trigger 4: Conflicting evidence ───────────────────────────────────────────

def test_conflicting_evidence_escalates():
    ev = [_t1_ev(supports=True), _t1_ev(supports=False)]
    decision, flags = decide(_question(), ev, _draft())
    assert decision == "ESCALATE"
    assert any("conflict" in f for f in flags)


def test_all_supporting_evidence_does_not_conflict():
    ev = [_t1_ev(supports=True), _t1_ev(supports=True)]
    decision, flags = decide(_question(), ev, _draft())
    assert decision == "AUTO_ANSWER"
    assert not any("conflict" in f for f in flags)


# ── Trigger 5: No cited evidence in draft ─────────────────────────────────────

def test_uncited_draft_escalates():
    decision, flags = decide(_question(), [_t1_ev()], _draft(evidence_ids=[]))
    assert decision == "ESCALATE"
    assert any("no linked evidence" in f for f in flags)


# ── Trigger 6: Stale evidence ─────────────────────────────────────────────────

def test_stale_evidence_escalates():
    old = (datetime.utcnow() - timedelta(days=STALENESS_DAYS + 1)).isoformat()
    ev = [Evidence(
        part_a_pid="PART-A", part_b_pid="PART-B", tier="T1",
        supports=True, source_name="Test", source_url="http://test.example",
        retrieved_at=old,
    )]
    decision, flags = decide(_question(), ev, _draft())
    assert decision == "ESCALATE"
    assert any("stale" in f for f in flags)


def test_fresh_evidence_does_not_flag_staleness():
    ev = [_t1_ev()]
    _, flags = decide(_question(), ev, _draft())
    assert not any("stale" in f for f in flags)


# ── Multiple flags reported together ──────────────────────────────────────────

def test_multiple_flags_all_reported():
    q = _question(part_a_confidence=0.5, question_type="licensing")
    decision, flags = decide(q, [], _draft(evidence_ids=[]))
    assert decision == "ESCALATE"
    # Expect: low conf, high liability, no T1, no cited evidence
    assert len(flags) >= 3
