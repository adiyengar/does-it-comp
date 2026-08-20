import json
import os
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def extract_parts(question: str) -> tuple[str, str]:
    """
    Extract the two products being compared from a free-form question.
    Returns (part_a, part_b) as raw strings for the resolver to canonicalize.
    """
    prompt = (
        f"Extract the two products being compared in this compatibility question.\n\n"
        f'Question: "{question}"\n\n'
        f"Return JSON only:\n"
        f'{{"part_a": "exact product name or model", "part_b": "exact product name or model"}}\n\n'
        f"Rules:\n"
        f"- Use the most specific name mentioned (include model numbers if present)\n"
        f"- If only one product is mentioned alongside a platform (Teams, Zoom, etc.), "
        f"the platform is part_b\n"
        f"- Return only the JSON, no other text"
    )
    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    try:
        data = json.loads(raw)
        return str(data.get("part_a", "")), str(data.get("part_b", ""))
    except (json.JSONDecodeError, KeyError):
        return "", ""
