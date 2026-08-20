# CLAUDE.md — Product Compatibility Agent (PoC)

## What this is

A demoable proof of concept for an agent that answers reseller product-compatibility questions ("can I connect device A to device B and will it work?"), assesses the risk of being wrong, and either answers with citations or escalates to a human.

**Audience for the demo:** internal stakeholders at a technology distributor. The person building this is a Product Manager, not the engineer who will eventually own it. The goal is to make the *concept* undeniable, not to ship production code.

**The core insight the demo must land:** this is a risk-ownership problem, not a lookup problem. Sales reps escalate these questions not because they can't find the answer but because they don't want to own being wrong. So the product's value is a cited, logged, institutionally-backed answer — and a *clean escalation* when the evidence isn't there.

**Escalation is not refusal.** The system never says "I don't know" and stops. It hands the question to a human with the research already done, and it captures what that human says. Every escalation is a handoff plus a data collection event. Language matters throughout the code and UI: escalate, route, hand off — never refuse, decline, or fail.

---

## Hard constraints

1. **Public data only.** Every data source must be publicly accessible without a corporate login or entitlement. No proprietary catalog data, no internal quote data, no customer data. If a source requires authentication, it is out of scope — tell me rather than working around it.
2. **No live external calls during a demo.** Fetch and snapshot source data into a local store once, via an explicit ingestion script. The demo runs entirely against local data. A demo that depends on a vendor website being up is a demo that fails in front of an audience.
3. **Be polite to sources.** Rate-limit ingestion, set a real User-Agent, cache aggressively, respect robots.txt. Check the terms of use on each source and flag anything that looks restrictive before writing the scraper.
4. **No fabricated data.** If a source can't be ingested, we build the demo with a smaller real dataset. Do not generate synthetic product data to fill gaps — a demo built on invented compatibility claims is worse than no demo. If you find yourself wanting to seed sample data, stop and ask.

---

## Non-negotiable design rules

These are the point of the project. If a rule is inconvenient, raise it with me — do not quietly relax it.

### 1. The risk gate is deterministic Python, never a prompt

The single most likely way this build goes wrong is that the gate becomes an instruction string like *"escalate if you are unsure."* That converts a hard engineering control into a suggestion the model can talk itself out of.

The gate is a pure function. Given a question record, a list of evidence records, and a draft answer, it returns `AUTO_ANSWER` or `ESCALATE`. It contains no LLM call. It is unit tested. Any one of these triggers escalation:

- SKU/part resolution confidence below threshold for either part
- Question type in the high-liability set (performance at scale, licensing, warranty, "other")
- No Tier-1 evidence present
- Two evidence records with contradictory `supports` values
- The draft answer contains a claim with no linked evidence ID
- Evidence older than the staleness threshold

### 2. Never ask the model how confident it is

Self-reported LLM confidence is not a usable abstention signal. Score the situation — evidence tier, question type, resolution confidence, source agreement — not the model's feelings about it.

### 3. Evidence tiers drive everything

| Tier | Meaning | Auto-answer? |
|---|---|---|
| T1 | Explicit vendor statement that these two specific parts are supported together | Yes |
| T2 | Derivable from published specs plus a standard | No |
| T3 | Inferred from co-occurrence | No |
| T4 | Nothing found | No |

Only T1 auto-answers in the PoC. **Tier is assigned by the retrieval tool, in code, not by the model.**

### 4. Every answer carries provenance

Answer ID, named source, source URL, retrieval date, and a scope disclaimer separating *"the vendor's published matrix lists this as supported"* from *"we warrant this will work in your environment."* An answer without a citation is a bug.

### 5. Four answer shapes, not two

1. **Confirmed** — yes, with citation
2. **Conditional** — yes, requires [adapter/firmware/version]
3. **Negative with alternative** — no, but these listed parts are supported
4. **Escalated** — with a pre-drafted answer and the specific uncertainty flagged

Shapes 2 and 3 are the commercially interesting ones. Don't collapse them into a bare yes/no.

---

## The escalation experience

Two failure modes to design against, and they pull in opposite directions:

- **Build a review queue and nobody logs in.** Solution experts will not adopt a new destination for work they already consider low value.
- **Send a plain email and get unstructured prose back.** Easy to adopt, impossible to learn from.

**The resolution: email is the transport, a structured screen is the mechanism.** Push the work to where the expert already is; make the action itself take thirty seconds on a deep link.

### The notification

Email (or Teams message) containing the **full draft answer in the body**, not a "you have a task waiting" stub. The expert must be able to judge correctness without clicking anything. Most of the value is them reading *"is this right?"* rather than doing research — that's what turns a 25-minute task into a 2-minute one.

Body contains:
```
Question:      Can [A] connect to [B]?    [from: rep name, account]
Resolved as:   [A-PID] (conf 0.97) · [B-PID] (conf 0.94)
Draft answer:  [proposed text]
Evidence:
  T1  Cisco TMG — supported with adapter CVR-X   (retrieved 2026-08-19)
  T2  B spec sheet lists 25W draw; A supplies 15W
WHY THIS CAME TO YOU:  sources conflict on power delivery.
                       Which governs?
[ Approve ]  [ Edit ]  [ Not my area ]
```

The "why this came to you" line is required. An escalation without a stated reason reads as the machine dumping work, which is exactly the dynamic we're trying to end.

### The action

Buttons are signed deep links — no login for Approve. Edit and correct open a single-purpose screen: no navigation, no dashboard, loads instantly, one question on it. The expert should never see a queue unless they go looking for one.

**Accept plain email replies as a fallback.** If someone just hits reply and types "no, that needs the QSFP adapter" — parse it, create the record, flag it as low-structure. A capture path that fails when used naturally will not be used at all.

### Routing

Route by vendor/domain specialty, not round-robin. Add a tiering rule: T1-with-minor-conflict goes to inside sales support; T3/T4 and liability-type questions go to solution experts. Most escalations should not reach a senior architect.

---

## Capturing expert answers as training data

This is the compounding asset. Design the capture schema before building the screen — the fields are the product.

### What to capture on every expert response

```
escalation_id
answer_final: str              # corrected or approved text
verdict: enum {approved, edited, rejected}
reason_code: enum              # REQUIRED — see below
sources_used: list[url]        # sources they consulted that we didn't have
tier_assigned: enum
conditions: list[str]
should_have_auto_answered: bool
time_to_respond: duration
reviewer_id
```

### The reason-code taxonomy is the highest-value field

It is also the field most likely to get dropped as "friction" during implementation. Do not drop it. Free-text corrections give you a pile of fixes and no idea what to improve; reason codes route directly to an owner:

| Reason code | What it fixes |
|---|---|
| `wrong_sku_resolved` | The entity resolver |
| `source_missing` | Ingestion backlog — **this is how we discover matrices we don't know exist** |
| `source_misread` | Retrieval parsing |
| `source_wrong` | Vendor data quality; needs a manual override record |
| `question_misclassified` | The classifier |
| `conditions_incomplete` | Draft prompt |
| `answer_correct_but_escalated` | The gate is too tight |

Make it one click — a row of chips, not a dropdown. `sources_used` is the sleeper field: experts know about compatibility documents we haven't found, and this is the cheapest possible discovery mechanism for them.

### Three datasets fall out of this

1. **Canonical answers** — every verified answer writes a `CanonicalAnswer` keyed on (part_a, part_b, question_type) with an `expires_at`. Next identical question is an instant cache hit. No ML required; this alone justifies the build.
2. **Gate calibration set** — `answer_correct_but_escalated` gives you false escalations; the monthly audit gives you false auto-answers. Together they let you move the gate thresholds on evidence rather than on vibes. **This is the only legitimate way coverage expands.**
3. **Entity resolution corrections** — every `wrong_sku_resolved` is a labeled disambiguation pair, directly reusable well beyond this agent.

### Do not

- Do not ask the expert to rate confidence on a 1–5 scale. Nobody does it honestly.
- Do not ask for a written explanation as a required field. Reason code required, free text optional.
- Do not auto-train on approvals without sampling. An approve click is weaker evidence than an edit — people approve to clear their inbox. Weight edits and rejections higher, and audit a sample of approvals.

---

## Stack

Chosen for demo speed and for a builder who is a capable beginner, not a professional engineer. Push back if something here is actively wrong, but don't swap the stack for personal preference.

- **Python 3.11+**, `uv` or `venv` for environment
- **SQLite** for the evidence store, question log, and answer cache — one file, zero setup, easy to inspect
- **Streamlit** for the UI
- **Anthropic API** for entity resolution, question classification, and answer drafting
- **pytest** for tests
- Keep dependencies minimal. Every new package needs a one-line justification.

No vector database, no Docker, no cloud services, no auth. If the PoC needs infrastructure, we've scoped it wrong.

---

## Data sources (all verified public)

Ingest into SQLite via `scripts/ingest_*.py`. Each writes a source record with `retrieved_at`.

**Lane 1 — Cisco optical transceivers ↔ network devices**
- Cisco TMG Compatibility Matrix: `tmgmatrix.cisco.com` — no login, exports to Excel
- `pytmg` on PyPI is an unofficial Python client. Try it, but **verify it still works before depending on it.** If it's broken, fall back to a manual Excel export from TMG committed to `data/raw/`.
- Cisco Optics-to-Optics matrix: `optics.cisco.com/iop`
- Cisco's own disclaimer says the data is informational and not a guarantee — reproduce that disclaimer in our output.

**Lane 2 — Microsoft Teams Rooms certified AV**
- `learn.microsoft.com/microsoftteams/rooms/certified-hardware` (Windows and Android)
- `learn.microsoft.com/microsoftteams/devices/teams-panels-certified-hardware`
- Public static HTML tables. This is the clean lane — certification is binary and authoritative.

**Do not add sources without asking.** Broadcom, NetApp, HPE, and Dell all have matrices but access models vary and several are gated. Two lanes is enough for a PoC.

---

## How to work with me

- I'm a Product Manager who has run large technical projects and understands architecture well, but I'm a beginner-level coder. Explain *why* before *what*. I will catch a bad product decision instantly and a bad Python idiom not at all.
- **Tell me when I'm wrong.** If I ask for something that will make the demo worse or the design incoherent, say so directly. I'd rather be corrected than agreed with.
- Small, reviewable commits with clear messages. I want to be able to follow the build.
- When you hit a real fork in the road (schema shape, how to handle a source that won't ingest, whether a rule should be code or config), stop and ask. Don't pick silently and mention it later.
- Don't write more than you need. A 200-line file I can read beats a 900-line file I can't.

---

## Workflow — use the `mattpocock/skills` toolkit

This repo is set up to use Matt Pocock's agent skills. Follow the chain rather than jumping to code:

1. **`/grill-me`** first. Before any code, interview me on the design. Push back on scope. I will over-scope this; your job is to stop me.
2. **`/to-spec`** — turn the outcome of that into a written spec in `docs/spec.md`.
3. **`/to-tickets`** — break it into tracer-bullet tickets with dependencies mapped. I want a visible plan before implementation starts.
4. **`/implement`** — build ticket by ticket.
5. **`/tdd`** for the risk gate specifically. Non-negotiable. The gate is the intellectual core of this product and it must have real tests: one test per escalation trigger, plus tests proving that a T1-only path auto-answers and a T3-only path never does.
6. **`/domain-modeling`** when we design the evidence and answer schemas — get these right early, they're expensive to change.
7. **`/code-review`** before each commit.

TDD is not required everywhere. It *is* required for `gate.py`.

---

## Repo shape

```
compatibility-agent-poc/
├── CLAUDE.md
├── docs/
│   ├── spec.md
│   └── demo-script.md
├── data/
│   ├── raw/              # committed source snapshots
│   └── app.db            # SQLite, gitignored
├── scripts/
│   ├── ingest_cisco_tmg.py
│   └── ingest_teams_certified.py
├── src/
│   ├── models.py         # question, evidence, answer, canonical answer
│   ├── resolve.py        # free text → vendor part ID
│   ├── classify.py       # question type
│   ├── retrieve.py       # source queries; assigns evidence tier
│   ├── draft.py          # LLM answer drafting, citation-enforced
│   ├── gate.py           # deterministic risk gate — no LLM
│   ├── escalate.py       # builds the packet, renders the notification
│   ├── capture.py        # expert response → training records
│   └── pipeline.py       # orchestration
├── tests/
│   ├── test_gate.py      # the important one
│   └── test_capture.py   # reason codes write correct records
└── app.py                # Streamlit: rep view · expert review view · audit view
```

For the PoC, **do not build real email infrastructure.** Render the notification email exactly as it would be sent and display it in the UI. The demoable artifact is the expert review screen and the captured record — not SMTP.

---

## Definition of done

The PoC is done when I can run `streamlit run app.py` and walk through `docs/demo-script.md` in five minutes, showing:

1. A question the agent **answers** — instant, cited, with a record ID
2. A question where it answers **conditionally** — "yes, but you need this adapter"
3. A question where it answers **negatively with an alternative** — "no, but these are supported"
4. A question it **escalates**, showing the rendered notification with the draft answer, the evidence found, and the stated reason it came to a human
5. The **expert review screen** — approve/edit, one-click reason code, captured in seconds
6. **The loop closing** — re-ask the same question and get an instant cited answer from the canonical cache, attributed to the expert who verified it
7. An **audit view** — every question, its risk score, gate decision, evidence, and (where applicable) who verified it

**Items 4 through 6 are the demo.** Run them as one unbroken ninety-second sequence: question escalates → expert answers in two clicks → same question now answered instantly. That sequence is the entire product thesis — the system gets smarter every time it doesn't know something. Anything can answer a question; the product is what happens when it shouldn't.

---

## Anti-goals

Do not build these, and tell me if I start asking for them:

- A general-purpose product Q&A chatbot
- A chat interface with conversation history — one question, one answer, one record
- User accounts, roles, or auth
- Any inference across vendors where no matrix exists
- A "confidence score" surfaced to the user as a percentage — it implies a precision we don't have
- Real email/SMTP integration, or a Teams app — render the notification, don't send it
- An expert-facing dashboard, workload view, or leaderboard. Experts get pushed one item at a time; a queue they must visit is the thing we're avoiding.
- Deployment, containers, or CI
- Coverage expansion. If the two lanes work, we're finished. Breadth is a Phase 2 conversation with a real engineering team.
