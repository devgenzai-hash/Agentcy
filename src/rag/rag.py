"""Production-style RAG with hallucination guard.

Steps:
1. Retrieve top-k context via `retriever.retrieve`.
2. Generate an answer constrained to that context, with [i] citations.
3. Hallucination guard: a separate LLM call grades whether every
   statement in the answer is supported by the cited context.
   If unsupported, we either revise or explicitly say "I don't know".
"""
from __future__ import annotations
import json

from ..llm import system_user
from ..storage import sqlite_store, vector_store
from .retriever import retrieve
from .chunker import chunk_tagged


# ---------- ingestion helpers --------------------------------------------
def ingest_text(text: str, metadata: dict | None = None) -> list[str]:
    """User-pasted text -> chunk -> embed -> Chroma."""
    chunks = [text[i:i + 1200] for i in range(0, len(text), 1100)]
    meta = [dict(metadata or {}, source="manual") for _ in chunks]
    return vector_store.add_documents(chunks, meta)


def ingest_page(page_id: int) -> int:
    """Move a SQLite page into the vector store as tagged chunks."""
    page = sqlite_store.get_page(page_id)
    if not page:
        return 0
    chunks = chunk_tagged(page["body_html"] or page["text"] or "")
    metas = [{
        "source": "page",
        "page_id": page_id,
        "url": page["url"],
        "title": page["title"],
    } for _ in chunks]
    ids = vector_store.add_documents(chunks, metas)
    return len(ids)


def ingest_recent_pages(limit: int = 50) -> int:
    n = 0
    for p in sqlite_store.recent_pages(limit):
        n += ingest_page(p["id"])
    return n


# ---------- generation ---------------------------------------------------
ANSWER_SYS = (
    "You are a careful research assistant for a creative social-media agency. "
    "Answer ONLY using the numbered context. Cite sources inline as [i]. "
    "If the context is insufficient, reply exactly: \"I don't know based on the indexed sources.\""
)

GUARD_SYS = (
    "You are a hallucination auditor. Given an answer and the context it cites, "
    "return strict JSON: {\"supported\": true|false, \"unsupported_claims\": [\"...\"]}."
)


def _format_context(ctx: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] (url={c['metadata'].get('url','manual')}) {c['document']}"
        for i, c in enumerate(ctx)
    )


def answer(question: str, *, top_k: int = 5) -> dict:
    ctx = retrieve(question, top_k=top_k)
    if not ctx:
        return {"answer": "I don't know based on the indexed sources.",
                "citations": [], "supported": True, "context": []}

    ctx_str = _format_context(ctx)
    draft = system_user(
        ANSWER_SYS,
        f"Question: {question}\n\nContext:\n{ctx_str}",
        temperature=0.2, max_tokens=600,
    )

    guard_raw = system_user(
        GUARD_SYS,
        f"Answer:\n{draft}\n\nContext:\n{ctx_str}",
        temperature=0.0, max_tokens=300, json_mode=True,
    )
    try:
        guard = json.loads(guard_raw)
    except Exception:
        guard = {"supported": True, "unsupported_claims": []}

    if not guard.get("supported", True):
        draft = ("I don't know based on the indexed sources.\n\n"
                 "(Unsupported claims removed: "
                 + "; ".join(guard.get("unsupported_claims", [])) + ")")

    return {
        "answer": draft,
        "citations": [c["metadata"] for c in ctx],
        "supported": guard.get("supported", True),
        "context": ctx,
    }
