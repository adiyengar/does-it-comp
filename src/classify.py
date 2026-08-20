import json
import os
import anthropic

QUESTION_TYPES = ["compatibility", "performance_at_scale", "licensing", "warranty", "other"]
HIGH_LIABILITY = {"performance_at_scale", "licensing", "warranty", "other"}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def classify(question_text: str) -> str:
    """Return one of QUESTION_TYPES."""
    prompt = (
        f'Classify this product question into exactly one category.\n\n'
        f'Question: "{question_text}"\n\n'
        f"Categories:\n"
        f"- compatibility: will these two products work together?\n"
        f"- performance_at_scale: throughput, load, or scale questions\n"
        f"- licensing: license, subscription, or entitlement questions\n"
        f"- warranty: warranty, support contract, or service coverage\n"
        f"- other: anything else\n\n"
        f'Respond with JSON only: {{"type": "compatibility"}}'
    )
    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    try:
        t = json.loads(raw).get("type", "other")
        return t if t in QUESTION_TYPES else "other"
    except (json.JSONDecodeError, KeyError):
        return "other"
