from dataclasses import dataclass, field
from datetime import datetime
import uuid


def _now() -> str:
    return datetime.utcnow().isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@dataclass
class Evidence:
    part_a_pid: str
    part_b_pid: str
    tier: str               # T1, T2, T3, T4
    source_name: str
    source_url: str
    retrieved_at: str
    supports: bool | None = None    # None for T4
    conditions: list[str] = field(default_factory=list)
    raw_text: str = ""
    id: str = field(default_factory=_uid)


@dataclass
class Question:
    raw_text: str
    part_a_raw: str
    part_b_raw: str
    question_type: str
    part_a_pid: str = ""
    part_b_pid: str = ""
    part_a_confidence: float = 0.0
    part_b_confidence: float = 0.0
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)


@dataclass
class Draft:
    shape: str              # confirmed, conditional, negative_with_alternative, escalated
    text: str
    evidence_ids: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


@dataclass
class Answer:
    question_id: str
    shape: str
    text: str
    evidence_ids: list[str]
    gate_decision: str      # AUTO_ANSWER or ESCALATE
    risk_flags: list[str]
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)


@dataclass
class CanonicalAnswer:
    part_a_pid: str
    part_b_pid: str
    question_type: str
    answer_text: str
    evidence_ids: list[str]
    verified_by: str
    verified_at: str
    id: str = field(default_factory=_uid)
    expires_at: str | None = None


@dataclass
class Escalation:
    question_id: str
    answer_id: str
    draft_text: str
    evidence_summary: list[dict]
    why_escalated: str
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
    resolved_at: str | None = None
    verdict: str | None = None


@dataclass
class ExpertResponse:
    escalation_id: str
    answer_final: str
    verdict: str            # approved, edited, rejected
    reason_code: str
    sources_used: list[str]
    tier_assigned: str
    conditions: list[str]
    should_have_auto_answered: bool
    time_to_respond: float  # seconds
    reviewer_id: str
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
