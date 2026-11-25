"""Use the LLM to assign a fine-grained category + field to each website.

Cheap to run because we only send the URL/domain (no page content),
preserving tokens as the user requested.
"""
from __future__ import annotations
import json
from urllib.parse import urlparse

from ..llm import system_user
from ..storage import sqlite_store


CATEGORIES = [
    "news_global", "news_regional", "tech_news", "ai_research",
    "marketing_creative", "social_trends", "video_short_form",
    "design_inspiration", "business_finance", "entertainment",
    "sports", "science", "lifestyle", "other",
]

SYSTEM = (
    "You are a strict website classifier. Given a list of URLs, "
    "return ONLY a JSON object mapping each URL to one category from this fixed list: "
    f"{CATEGORIES}. No prose."
)


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def categorize_all(batch_size: int = 25) -> dict[str, str]:
    sites = sqlite_store.list_websites()
    urls = [s["url"] for s in sites]
    mapping: dict[str, str] = {}
    for batch in _chunks(urls, batch_size):
        user = "URLs:\n" + "\n".join(batch)
        raw = system_user(SYSTEM, user, temperature=0.0, max_tokens=800, json_mode=True)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # last-ditch: try to find first {...}
            start, end = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[start:end + 1]) if start != -1 else {}
        for url in batch:
            cat = data.get(url) if isinstance(data, dict) else None
            if cat in CATEGORIES:
                mapping[url] = cat

    # persist
    for s in sites:
        cat = mapping.get(s["url"])
        if not cat:
            continue
        sqlite_store.upsert_website(
            url=s["url"], domain=s["domain"], field=s["field"], category=cat
        )
    return mapping
