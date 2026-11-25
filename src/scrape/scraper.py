"""Async website scraper.

Design goals (per the user's brief):
- store raw text along with the HTML tag as identifier
- preserve only meaningful structural tags (h1..h3, p, li, a, blockquote, title)
  -> drops scripts/styles/nav cruft so we don't waste tokens later
- write each page once into SQLite (raw + cleaned + tag map)
"""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from selectolax.parser import HTMLParser

from ..config import settings
from ..storage import sqlite_store


KEEP_TAGS = ("title", "h1", "h2", "h3", "p", "li", "a", "blockquote")
DROP_TAGS = ("script", "style", "noscript", "iframe", "svg", "footer", "nav")


@dataclass
class ScrapeResult:
    url: str
    title: str
    text: str
    body_html: str
    tags: dict[str, list[str]]


def parse_html(url: str, html: str) -> ScrapeResult:
    tree = HTMLParser(html)
    for tag in DROP_TAGS:
        for n in tree.css(tag):
            n.decompose()

    title_node = tree.css_first("title")
    title = title_node.text(strip=True) if title_node else url

    tag_map: dict[str, list[str]] = {t: [] for t in KEEP_TAGS}
    body_chunks: list[str] = []
    text_chunks: list[str] = []

    for tag in KEEP_TAGS:
        for node in tree.css(tag):
            txt = node.text(separator=" ", strip=True)
            if not txt or len(txt) < 2:
                continue
            tag_map[tag].append(txt)
            # tag-as-identifier: keep the tag wrapped form for storage
            body_chunks.append(f"<{tag}>{txt}</{tag}>")
            text_chunks.append(txt)

    return ScrapeResult(
        url=url,
        title=title[:500],
        body_html="\n".join(body_chunks),
        text="\n".join(text_chunks),
        tags={k: v for k, v in tag_map.items() if v},
    )


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=settings.scrape_timeout,
                             follow_redirects=True,
                             headers={"User-Agent": settings.user_agent})
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", "text/html"):
            return None
        return r.text
    except Exception:
        return None


async def _scrape_one(client: httpx.AsyncClient, sem: asyncio.Semaphore,
                      website_id: int | None, url: str) -> dict | None:
    async with sem:
        html = await _fetch(client, url)
    if not html:
        return None
    res = parse_html(url, html)
    page_id = sqlite_store.insert_page(
        website_id=website_id, url=res.url, title=res.title,
        body_html=res.body_html, text=res.text, tags=res.tags,
    )
    return {"page_id": page_id, "url": url, "title": res.title, "chars": len(res.text)}


async def scrape_urls(items: list[tuple[int | None, str]]) -> list[dict]:
    """items = list of (website_id_or_None, url)."""
    sem = asyncio.Semaphore(settings.scrape_concurrency)
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [_scrape_one(client, sem, wid, url) for wid, url in items]
        results = await asyncio.gather(*tasks)
    return [r for r in results if r]


def scrape_field(field: str) -> list[dict]:
    """Scrape every site stored under a given field bucket."""
    sites = sqlite_store.list_websites(field=field)
    items = [(s["id"], s["url"]) for s in sites]
    return asyncio.run(scrape_urls(items))


def scrape_all_chunked(chunk_size: int = 10) -> list[dict]:
    sites = sqlite_store.list_websites()
    items = [(s["id"], s["url"]) for s in sites]
    out: list[dict] = []
    for i in range(0, len(items), chunk_size):
        out.extend(asyncio.run(scrape_urls(items[i:i + chunk_size])))
    return out
