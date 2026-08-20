import json
import os
import anthropic
from .models import Draft, Evidence, Question

_client: anthropic.Anthropic | None = None

SYSTEM = (
    "You are a product compatibility assistant for a technology distributor. "
    "Draft concise answers based only on the evidence provided. "
    "Every factual claim MUST be followed by a citation like [ev-ID]. "
    "Do not invent information not in the evidence. "
    "Return JSON only — no markdown fences."
)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def draft(question: Question, evidence: list[Evidence], alternatives: list[str]) -> Draft:
    if not evidence:
        return Draft(shape="escalated", text="No evidence found to support an answer.", evidence_ids=[])

    ev_block = "\n".join(
        f"[{e.id}] Tier={e.tier} Source={e.source_name} "
        f"Supports={e.supports} Conditions={e.conditions} Snippet={e.raw_text[:200]}"
        for e in evidence
    )
    alt_block = f"\nKnown alternatives for {question.part_b_pid}: {alternatives}" if alternatives else ""

    prompt = (
        f"Question: {question.raw_text}\n"
        f"Part A: {question.part_a_pid}\n"
        f"Part B: {question.part_b_pid}\n\n"
        f"Evidence:\n{ev_block}{alt_block}\n\n"
        f"Choose the appropriate answer shape:\n"
        f'- "confirmed": T1 evidence says compatible, no conditions\n'
        f'- "conditional": compatible but requires adapter/firmware/config\n'
        f'- "negative_with_alternative": not compatible, but alternatives exist\n'
        f'- "escalated": evidence insufficient or conflicting\n\n'
        f"Return JSON:\n"
        f'{{"shape":"confirmed","text":"Answer with [ev-ID] citations.","evidence_ids":["ev-id"],"alternatives":[]}}'
    )

    resp = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    try:
        data = json.loads(raw)
        return Draft(
            shape=data.get("shape", "escalated"),
            text=data.get("text", ""),
            evidence_ids=data.get("evidence_ids", []),
            alternatives=data.get("alternatives", []),
        )
    except (json.JSONDecodeError, KeyError):
        return Draft(shape="escalated", text=raw, evidence_ids=[])
