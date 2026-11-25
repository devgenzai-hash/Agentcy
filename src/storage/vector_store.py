"""Chroma vector store wrapper.

Uses an explicit embedding function backed by our pluggable embedding
client (NIM by default), so the vector DB stays in sync with whichever
provider the user configures.
"""
from __future__ import annotations
import os
import uuid
from typing import Sequence

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from ..config import settings
from ..llm.embeddings import embed


class _ConfiguredEmbedder(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (chroma signature)
        return embed(list(input))


def _client() -> chromadb.api.ClientAPI:
    os.makedirs(settings.chroma_path, exist_ok=True)
    return chromadb.PersistentClient(path=settings.chroma_path)


def collection(name: str = "knowledge"):
    return _client().get_or_create_collection(
        name=name,
        embedding_function=_ConfiguredEmbedder(),
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(
    docs: Sequence[str],
    metadatas: Sequence[dict] | None = None,
    ids: Sequence[str] | None = None,
    *,
    name: str = "knowledge",
) -> list[str]:
    if not docs:
        return []
    ids = list(ids) if ids else [str(uuid.uuid4()) for _ in docs]
    metadatas = list(metadatas) if metadatas else [{} for _ in docs]
    collection(name).add(documents=list(docs), metadatas=metadatas, ids=ids)
    return ids


def query(text: str, k: int = 8, *, name: str = "knowledge",
          where: dict | None = None) -> list[dict]:
    res = collection(name).query(query_texts=[text], n_results=k, where=where)
    out = []
    for i, doc in enumerate(res["documents"][0]):
        out.append({
            "id": res["ids"][0][i],
            "document": doc,
            "metadata": res["metadatas"][0][i],
            "distance": res["distances"][0][i] if "distances" in res else None,
        })
    return out


def count(name: str = "knowledge") -> int:
    return collection(name).count()
