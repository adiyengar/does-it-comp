import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import streamlit as st

from src.capture import get_canonical, save_canonical, save_expert_response
from src.db import get_conn, init_db
from src.escalate import get_escalation
from src.extract import extract_parts
from src.models import CanonicalAnswer, ExpertResponse
from src.pipeline import run as run_pipeline
from src.seed import seed_if_empty

init_db()
seed_if_empty()
st.set_page_config(page_title="Compatibility Agent PoC", layout="wide")

REASON_CODES = [
    "answer_correct_but_escalated",
    "conditions_incomplete",
    "question_misclassified",
    "source_missing",
    "source_misread",
    "source_wrong",
    "wrong_sku_resolved",
]

SHAPE_DISPLAY = {
    "confirmed": ("Confirmed compatible", "success"),
    "conditional": ("Compatible — with conditions", "warning"),
    "negative_with_alternative": ("Not compatible — alternatives available", "error"),
    "escalated": ("Routed to expert", "warning"),
}

# ── Expert Review (deep link: ?escalation_id=xxx) ─────────────────────────────
params = st.query_params
if "escalation_id" in params:
    esc_id = params["escalation_id"]
    esc = get_escalation(esc_id)

    if esc is None:
        st.error(f"Escalation `{esc_id}` not found.")
        st.stop()

    if "review_start" not in st.session_state:
        st.session_state.review_start = datetime.utcnow()

    created = datetime.fromisoformat(esc["created_at"]).strftime("%Y-%m-%d %H:%M UTC")
    st.title("Expert Review")
    st.caption(f"Escalation `{esc_id[:12]}…`  ·  {created}")

    st.markdown("**Why this came to you:**")
    st.info(esc["why_escalated"])

    st.markdown("**Draft answer (pre-researched):**")
    st.code(esc["draft_text"], language=None)

    ev_summary = json.loads(esc["evidence_summary"])
    if ev_summary:
        st.markdown("**Evidence considered:**")
        for e in ev_summary:
            cond = f" — conditions: {', '.join(e['conditions'])}" if e.get("conditions") else ""
            st.markdown(f"- `{e['tier']}` [{e['source']}]({e['url']}){cond}")

    if esc["verdict"]:
        st.success(f"Already resolved: **{esc['verdict']}**")
        st.stop()

    st.divider()
    st.markdown("**Your response** (takes ~30 seconds):")
    answer_final = st.text_area("Answer text", value=esc["draft_text"], height=100)

    col1, col2 = st.columns(2)
    verdict = col1.radio("Verdict", ["approved", "edited", "rejected"], horizontal=True)
    tier = col2.selectbox("Evidence tier you found", ["T1", "T2", "T3", "T4"])

    st.markdown("**Reason code** (one click — required):")
    reason_code = st.radio("", REASON_CODES, horizontal=True, label_visibility="collapsed")

    sources = st.text_input("Sources you consulted (URLs, comma-separated)", placeholder="Optional")
    conditions_text = st.text_input("Conditions / caveats (comma-separated)", placeholder="Optional")
    should_auto = st.checkbox("The system should have auto-answered this")

    if st.button("Submit response", type="primary"):
        elapsed = (datetime.utcnow() - st.session_state.review_start).total_seconds()
        resp = ExpertResponse(
            escalation_id=esc_id,
            answer_final=answer_final,
            verdict=verdict,
            reason_code=reason_code,
            sources_used=[s.strip() for s in sources.split(",") if s.strip()],
            tier_assigned=tier,
            conditions=[c.strip() for c in conditions_text.split(",") if c.strip()],
            should_have_auto_answered=should_auto,
            time_to_respond=elapsed,
            reviewer_id="demo-expert",
        )
        save_expert_response(resp)

        if verdict != "rejected":
            with get_conn() as conn:
                q_row = conn.execute(
                    "SELECT * FROM questions WHERE id = "
                    "(SELECT question_id FROM escalations WHERE id = ?)",
                    (esc_id,),
                ).fetchone()
            if q_row:
                # Use resolved PID when available; fall back to raw text (mirrors pipeline logic)
                eff_a = q_row["part_a_pid"] or q_row["part_a_raw"].strip()
                eff_b = q_row["part_b_pid"] or q_row["part_b_raw"].strip()
                ca = CanonicalAnswer(
                    part_a_pid=eff_a,
                    part_b_pid=eff_b,
                    question_type=q_row["question_type"],
                    answer_text=answer_final,
                    evidence_ids=[],
                    verified_by="demo-expert",
                    verified_at=datetime.utcnow().isoformat(),
                )
                save_canonical(ca)

        st.success("Response captured. The next identical question answers instantly from cache.")
        st.balloons()
    st.stop()

# ── Sidebar navigation ────────────────────────────────────────────────────────
view = st.sidebar.radio("View", ["Ask a Question", "Audit Log"])

# ── Rep View ─────────────────────────────────────────────────────────────────
if view == "Ask a Question":
    st.title("Product Compatibility Agent")
    st.caption("Ask a compatibility question in plain language. Cited answer or expert escalation — never a guess.")

    with st.form("query_form"):
        question = st.text_input(
            "Your question",
            placeholder="e.g. Can I use a Logitech Rally Bar with Teams?",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Check compatibility →", type="primary", use_container_width=True)

    if submitted and question.strip():
        result = None

        with st.status("Checking compatibility…", expanded=True) as status:
            st.write("Identifying products…")
            part_a, part_b = extract_parts(question)
            if part_a and part_b:
                st.write(f"Checking **{part_a}** ↔ **{part_b}**")
            else:
                st.write("Couldn't identify two products — routing to expert.")

            st.write("Searching evidence…")
            result = run_pipeline(question, part_a or question, part_b or question)
            status.update(label="Done", state="complete", expanded=False)

        src = result["source"]

        if src == "cache":
            st.success("Instant answer — expert-verified, served from cache")
            st.caption(
                f"Verified by {result.get('verified_by', 'expert')} "
                f"· {result.get('verified_at', '')[:10]}"
            )
            st.markdown(result["text"])

        elif src == "auto":
            label, level = SHAPE_DISPLAY.get(result["shape"], ("Answer", "info"))
            getattr(st, level)(label)
            st.markdown(result["text"])

            evs = result.get("evidence", [])
            if evs:
                with st.expander(f"Evidence ({len(evs)} source{'s' if len(evs) != 1 else ''})"):
                    for e in evs:
                        cond = f" — {', '.join(e['conditions'])}" if e.get("conditions") else ""
                        st.markdown(f"**{e['tier']}** · [{e['source']}]({e['url']}){cond}")

            st.caption(f"Record `{result['question_id']}`")

        elif src == "escalation":
            esc_id = result["escalation_id"]
            deep_link = f"?escalation_id={esc_id}"

            st.warning("Routed to expert for review")
            st.markdown(f"**Expert review →** [{deep_link}]({deep_link})")

            with st.expander("Rendered notification (as it would be sent)"):
                st.code(result["notification"], language=None)

            with st.expander("Why it was escalated"):
                for flag in result.get("risk_flags", []):
                    st.markdown(f"- {flag}")

            st.caption(f"Escalation `{esc_id}`")

# ── Audit Log ─────────────────────────────────────────────────────────────────
else:
    st.title("Audit Log")
    st.caption("Every question, its gate decision, evidence, and outcome.")

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                q.created_at, q.raw_text, q.part_a_pid, q.part_b_pid,
                q.question_type, q.part_a_confidence, q.part_b_confidence,
                a.shape, a.gate_decision, a.risk_flags,
                e.id AS esc_id, e.verdict,
                er.reviewer_id, er.reason_code
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN escalations e ON e.question_id = q.id
            LEFT JOIN expert_responses er ON er.escalation_id = e.id
            ORDER BY q.created_at DESC
            LIMIT 200
            """
        ).fetchall()

    if not rows:
        st.info("No questions yet. Ask one in 'Ask a Question'.")
    else:
        import pandas as pd

        data = [
            {
                "Date": r["created_at"][:16],
                "Question": r["raw_text"][:55],
                "Part A": r["part_a_pid"] or "—",
                "Conf A": f"{r['part_a_confidence']:.2f}" if r["part_a_confidence"] else "—",
                "Part B": r["part_b_pid"] or "—",
                "Conf B": f"{r['part_b_confidence']:.2f}" if r["part_b_confidence"] else "—",
                "Type": r["question_type"],
                "Shape": r["shape"] or "—",
                "Gate": r["gate_decision"] or "—",
                "Escalated": "Yes" if r["esc_id"] else "No",
                "Verdict": r["verdict"] or "—",
                "Reviewer": r["reviewer_id"] or "—",
                "Reason": r["reason_code"] or "—",
            }
            for r in rows
        ]
        st.dataframe(pd.DataFrame(data), use_container_width=True)
