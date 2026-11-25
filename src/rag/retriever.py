"""Hybrid retriever with LLM-based reranking.

Pipeline:
1. Vector recall (k_vector) from Chroma.
2. Lexical recall (k_bm25) over the same candidate pool to boost
   exact-term matches the embedder may miss.
3. LLM rerank: ask the model to score each candidate 0-10 for
   relevance and return the top-k.
"""
from __future__ import annotations
import json
import re

from rank_bm25 import BM25Okapi

from ..llm import system_user
from ..storage import vector_store


_TOKEN = re.compile(r"\w+")


def _tok(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s)]


def vector_recall(question: str, k: int = 20, collection: str = "knowledge") -> list[dict]:
    return vector_store.query(question, k=k, name=collection)


def bm25_rerank(question: str, candidates: list[dict], k: int = 10) -> list[dict]:
    if not candidates:
        return []
    corpus = [_tok(c["document"]) for c in candidates]
    bm = BM25Okapi(corpus)
    scores = bm.get_scores(_tok(question))
    for c, s in zip(candidates, scores):
        c["bm25"] = float(s)
    candidates.sort(key=lambda c: c["bm25"], reverse=True)
    return candidates[:k]


_RERANK_SYS = (
    "You are a relevance grader. For each candidate snippet, rate how well "
    "it answers the user question on a 0-10 integer scale (10 = directly "
    "answers, 0 = irrelevant). Return strict JSON: "
    '{"scores":[{"i":0,"score":0}, ...]}'
)


def llm_rerank(question: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    if not candidates:
        return []
    listing = "\n".join(
        f"[{i}] {c['document'][:600]}" for i, c in enumerate(candidates)
    )
    raw = system_user(_RERANK_SYS,
                      f"Question: {question}\n\nCandidates:\n{listing}",
                      temperature=0.0, max_tokens=400, json_mode=True)
    try:
        data = json.loads(raw)
        scores = {int(s["i"]): float(s["score"]) for s in data.get("scores", [])}
    except Exception:
        scores = {}
    for i, c in enumerate(candidates):
        c["llm_score"] = scores.get(i, 0.0)
    candidates.sort(key=lambda c: c["llm_score"], reverse=True)
    return candidates[:top_k]


def retrieve(question: str, *, top_k: int = 5, collection: str = "knowledge") -> list[dict]:
    vec = vector_recall(question, k=20, collection=collection)
    lex = bm25_rerank(question, vec, k=10)
    return llm_rerank(question, lex, top_k=top_k)
