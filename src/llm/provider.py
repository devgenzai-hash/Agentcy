"""Unified chat-completion client.

All supported providers expose an OpenAI-compatible HTTP API
(NVIDIA NIM, OpenRouter, Ollama, llama.cpp server, OpenAI), so we
delegate to the openai SDK and only swap base_url / api_key.
"""
from __future__ import annotations
from typing import Iterable
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import settings, resolve_base_url


def _client() -> OpenAI:
    print("=" * 60)
    print("Provider:", repr(settings.ai_provider))
    print("Base URL override:", repr(settings.ai_base_url))
    print("Resolved URL:", repr(resolve_base_url(settings.ai_provider, settings.ai_base_url)))
    print("Model:", repr(settings.ai_model))
    print("=" * 60)
    
    return OpenAI(
        api_key=settings.ai_api_key or "EMPTY",
        base_url=resolve_base_url(settings.ai_provider, settings.ai_base_url),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    """Send a chat-completion request and return the assistant text."""
    kwargs = dict(
        model=model or settings.ai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        # Most providers accept this; harmless if ignored.
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client().chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def system_user(system: str, user: str, **kw) -> str:
    return chat(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}],
        **kw,
    )
