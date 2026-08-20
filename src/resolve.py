import json
import os
import re
import anthropic
from .db import get_conn

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _normalize(s: str) -> str:
    """Strip spaces, hyphens, dots; lowercase — for fuzzy comparison."""
    return re.sub(r"[\s\-\./]", "", s.lower())


def known_pids() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT part_a_pid FROM evidence "
            "UNION SELECT DISTINCT part_b_pid FROM evidence"
        ).fetchall()
    return [r[0] for r in rows]


def resolve(text: str) -> tuple[str, float]:
    """Return (canonical_pid, confidence 0–1). Returns ('', 0.0) if no match."""
    pids = known_pids()
    if not pids:
        return "", 0.0

    # Exact match
    upper = text.strip().upper()
    for pid in pids:
        if pid.upper() == upper:
            return pid, 1.0

    # Normalized match: ignore spaces / hyphens / dots ("Microsoft Teams Rooms" → "Microsoft-Teams-Rooms")
    norm = _normalize(text)
    for pid in pids:
        if _normalize(pid) == norm:
            return pid, 0.99

    # Substring: only shortcut if exactly one PID contains the input — else let Claude disambiguate
    if norm:
        substr_matches = [pid for pid in pids if norm in _normalize(pid)]
        if len(substr_matches) == 1:
            return substr_matches[0], 0.90

    prompt = (
        f"You are a product catalog resolver for network and AV hardware.\n\n"
        f"Known part IDs (sample):\n{chr(10).join(pids[:300])}\n\n"
        f'User input: "{text}"\n\n'
        f"Which known part ID does the user mean? Respond with JSON only:\n"
        f'{{"pid": "EXACT-PID-FROM-LIST", "confidence": 0.95}}\n\n'
        f"Rules:\n"
        f"- Return only a pid that appears verbatim in the list above.\n"
        f"- If no match, return {{\"pid\": \"\", \"confidence\": 0.0}}\n"
        f"- Return only the JSON, no other text."
    )

    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    try:
        data = json.loads(raw)
        pid = str(data.get("pid", ""))
        conf = float(data.get("confidence", 0.0))
        if pid and pid not in pids:
            return "", 0.0
        return pid, conf
    except (json.JSONDecodeError, ValueError):
        return "", 0.0
