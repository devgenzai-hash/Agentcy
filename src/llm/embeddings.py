"""Embedding client (OpenAI-compatible)."""
from __future__ import annotations
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings, resolve_base_url


def _client() -> OpenAI:
    return OpenAI(
        api_key=settings.embedding_api_key or "EMPTY",
        base_url=resolve_base_url(settings.embedding_provider, settings.embedding_base_url),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    # NVIDIA NIM embedqa models accept an "input_type" extra param; pass via extra_body.
    extra = {}
    if "embedqa" in (model or settings.embedding_model):
        extra = {"input_type": "passage"}
    resp = _client().embeddings.create(
        model=model or settings.embedding_model,
        input=texts,
        extra_body=extra or None,
    )
    return [d.embedding for d in resp.data]


def embed_query(text: str) -> list[float]:
    extra = {}
    if "embedqa" in settings.embedding_model:
        extra = {"input_type": "query"}
    resp = _client().embeddings.create(
        model=settings.embedding_model,
        input=[text],
        extra_body=extra or None,
    )
    return resp.data[0].embedding
