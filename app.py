"""Streamlit control panel for the AgentSwarm creative agency."""
from __future__ import annotations
import queue
import streamlit as st

from src.storage import sqlite_store, vector_store
from src.scrape import scraper
from src.agency import orchestrator
from src.rag import answer, ingest_text, ingest_recent_pages
from src.hitl import set_handler

st.set_page_config(page_title="AgentSwarm", layout="wide")
st.title("AgentSwarm – AI Creative Social-Media Agency")

# ---------- HITL queue wired into Streamlit -----------------------------
if "hitl_q" not in st.session_state:
    st.session_state.hitl_q = queue.Queue()
    st.session_state.hitl_answers = {}

def _hitl_ui(agent: str, question: str) -> str:
    # Synchronous: drop the question on a list so the user can answer in the
    # sidebar; for the MVP we auto-skip if no answer given within 0.1s.
    st.session_state.hitl_q.put({"agent": agent, "question": question})
    return st.session_state.hitl_answers.pop(agent, "")

set_handler(_hitl_ui)

# ---------- sidebar: pipeline controls ----------------------------------
with st.sidebar:
    st.header("Pipeline")
    if st.button("1. Init DB + seed websites"):
        sqlite_store.init_db()
        st.success(orchestrator.bootstrap_websites())
    if st.button("2. AI categorize websites"):
        st.success(orchestrator.categorize_websites())
    field = st.selectbox("Field to scrape", sorted({s["field"] for s in sqlite_store.list_websites()} or {"news_global"}))
    if st.button("3. Scrape selected field"):
        with st.spinner("Scraping..."):
            r = orchestrator.scrape_field(field)
        st.success(f"Scraped {len(r['results'])} pages from {field}")
    if st.button("4. Index recent pages -> Vector DB"):
        with st.spinner("Embedding..."):
            n = ingest_recent_pages(limit=200)
        st.success(f"Indexed {n} chunks (total in DB: {vector_store.count()})")
    if st.button("5. Collect trending (YT / X / IG / Google)"):
        with st.spinner("Collecting trends..."):
            t = orchestrator.collect_trends()
        st.success({k: len(v) for k, v in t.items()})

    st.divider()
    st.header("HITL queue")
    pending: list[dict] = []
    while not st.session_state.hitl_q.empty():
        pending.append(st.session_state.hitl_q.get())
    for q in pending:
        ans = st.text_input(f"{q['agent']}: {q['question']}", key=f"hitl-{q['agent']}")
        if ans:
            st.session_state.hitl_answers[q["agent"]] = ans

# ---------- main tabs ---------------------------------------------------
tab_inject, tab_ask, tab_agency, tab_data = st.tabs(
    ["Inject knowledge", "Ask RAG", "Run agency", "Browse data"]
)

with tab_inject:
    st.subheader("Paste text and embed into the vector DB")
    txt = st.text_area("Text", height=200, placeholder="Paste research, notes, transcripts, briefs...")
    src = st.text_input("Source label (optional)", value="manual")
    if st.button("Embed and store"):
        ids = ingest_text(txt, metadata={"source": src})
        st.success(f"Stored {len(ids)} chunks. Vector DB now: {vector_store.count()}")

with tab_ask:
    st.subheader("Ask the knowledge base (RAG with rerank + hallucination guard)")
    q = st.text_input("Question", value="What is currently trending in tech?")
    k = st.slider("Top-k context", 1, 10, 5)
    if st.button("Answer"):
        with st.spinner("Retrieving + grading..."):
            out = answer(q, top_k=k)
        st.markdown("### Answer")
        st.write(out["answer"])
        st.caption(f"Supported by sources: {out['supported']}")
        with st.expander("Citations / context"):
            for i, c in enumerate(out["context"]):
                st.markdown(f"**[{i}]** {c['metadata'].get('url','manual')}")
                st.code(c["document"][:800])

with tab_agency:
    st.subheader("Run the multi-agent agency")
    goal = st.text_input(
        "Goal for the lead manager",
        value="Find a viral video idea in personal finance for Gen-Z on Instagram Reels.",
    )
    workers = st.slider("Workers per department", 1, 4, 2)
    if st.button("Run agency"):
        with st.spinner("Agents are collaborating..."):
            out = orchestrator.run_agency(goal, workers_per_dept=workers)
        st.markdown("### Final deliverable")
        st.write(out["final"])
        with st.expander("Plan"):
            st.json(out["plan"])
        with st.expander("Per-department reports"):
            for r in out["results"]:
                st.markdown(f"#### {r['field']}")
                st.write(r["summary"])
                for f in r["findings"]:
                    st.caption(f["worker"])
                    st.write(f["report"])

with tab_data:
    st.subheader("Websites")
    st.dataframe(sqlite_store.list_websites())
    st.subheader("Recent scraped pages")
    st.dataframe(sqlite_store.recent_pages(50))
    st.subheader("Trends (latest 50)")
    st.dataframe(sqlite_store.recent_trends(limit=50))
    st.subheader("Agent message log")
    st.dataframe(sqlite_store.recent_messages(100))
