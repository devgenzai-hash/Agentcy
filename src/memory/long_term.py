"""Long-term memory: durable facts in SQLite + semantic recall via Chroma."""
from __future__ import annotations
from ..storage import sqlite_store, vector_store


_COLLECTION = "agent_memory"


def remember(agent: str, kind: str, content: str) -> None:
    sqlite_store.remember(agent, kind, content)
    vector_store.add_documents(
        [content],
        metadatas=[{"agent": agent, "kind": kind, "source": "memory"}],
        name=_COLLECTION,
    )


def recall_recent(agent: str | None = None, limit: int = 20) -> list[dict]:
    return sqlite_store.recall(agent=agent, limit=limit)


def recall_semantic(query: str, agent: str | None = None, k: int = 5) -> list[dict]:
    where = {"agent": agent} if agent else None
    return vector_store.query(query, k=k, name=_COLLECTION, where=where)
