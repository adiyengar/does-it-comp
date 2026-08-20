# Demo Script

Five-minute walkthrough covering all four answer shapes.

## Setup (before the audience arrives)

```bash
# Install dependencies
uv sync --dev

# Ingest data (Teams certified hardware — takes ~15s)
uv run python scripts/ingest_teams_certified.py

# Optional: Cisco TMG (try pytmg or paste Excel export into data/raw/)
uv run python scripts/ingest_cisco_tmg.py

# Run
ANTHROPIC_API_KEY=sk-... uv run streamlit run app.py
```

---

## The ninety-second core sequence (items 4–6)

This is the sequence that demonstrates the product thesis. Run it unbroken.

### Step 1 — Escalation (30 seconds)

Ask about a product pair where only T2/T3 evidence exists, or where parts can't be resolved:

> **Question:** Can the Logitech Rally Bar work with a Cisco Catalyst 9300?
> **Product A:** Logitech Rally Bar
> **Product B:** Cisco Catalyst 9300

Expected: the gate escalates. The screen shows the rendered notification with draft answer, evidence found, and the stated reason.

Point out the "why this came to you" line — that's the anti-dumping feature.

### Step 2 — Expert review (30 seconds)

Click the expert review deep link. The review screen loads with:
- The full draft answer pre-written
- A one-click reason code row
- A 30-second action, not a research task

Select verdict, click a reason code chip, hit Submit.

### Step 3 — Cache hit (5 seconds)

Go back to "Ask a Question". Ask the exact same question:

> **Question:** Can the Logitech Rally Bar work with a Cisco Catalyst 9300?

Expected: instant answer, "Verified by demo-expert on [today]." No LLM call. No latency.

**This is the product.** The system got smarter.

---

## Other demo paths

### Confirmed answer

Ask about a Teams-certified device with the platform:

> **Question:** Is the [device name from certified list] compatible with Microsoft Teams Rooms?
> **Product A:** [exact device name]
> **Product B:** Microsoft-Teams-Rooms

Expected: Confirmed answer with T1 citation.

### Audit log

Switch to Audit Log in the sidebar. Show every question, gate decision, escalation status, and reviewer. This is the institutional record — every answer is backed by a named source and a log entry.

---

## What to say during the demo

> "Sales reps escalate these questions not because they can't find the answer — it's because they don't want to own being wrong. What we're building is institutional ownership of the answer, plus a clean handoff when we shouldn't own it.

> Notice the system never says 'I don't know.' It either answers with a citation, or it hands the question to the right person with the research already done and a specific question: 'which of these sources governs?'

> The compounding value is that third screen — the same question, answered instantly. Every escalation funds the next auto-answer. The gate gets tighter on evidence, not on vibes."
