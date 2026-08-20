import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    part_a_pid TEXT NOT NULL,
    part_b_pid TEXT NOT NULL,
    tier TEXT NOT NULL,
    supports INTEGER,
    conditions TEXT NOT NULL DEFAULT '[]',
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    raw_text TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    raw_text TEXT NOT NULL,
    part_a_raw TEXT NOT NULL,
    part_b_raw TEXT NOT NULL,
    part_a_pid TEXT DEFAULT '',
    part_b_pid TEXT DEFAULT '',
    part_a_confidence REAL DEFAULT 0.0,
    part_b_confidence REAL DEFAULT 0.0,
    question_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    shape TEXT NOT NULL,
    text TEXT NOT NULL,
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    gate_decision TEXT NOT NULL,
    risk_flags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_answers (
    id TEXT PRIMARY KEY,
    part_a_pid TEXT NOT NULL,
    part_b_pid TEXT NOT NULL,
    question_type TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    verified_by TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    expires_at TEXT,
    UNIQUE(part_a_pid, part_b_pid, question_type)
);

CREATE TABLE IF NOT EXISTS escalations (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    answer_id TEXT NOT NULL,
    draft_text TEXT NOT NULL,
    evidence_summary TEXT NOT NULL DEFAULT '[]',
    why_escalated TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    verdict TEXT
);

CREATE TABLE IF NOT EXISTS expert_responses (
    id TEXT PRIMARY KEY,
    escalation_id TEXT NOT NULL,
    answer_final TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    sources_used TEXT NOT NULL DEFAULT '[]',
    tier_assigned TEXT NOT NULL,
    conditions TEXT NOT NULL DEFAULT '[]',
    should_have_auto_answered INTEGER NOT NULL,
    time_to_respond REAL NOT NULL,
    reviewer_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
