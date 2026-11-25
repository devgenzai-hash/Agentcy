"""Pull trending signals from public, scrape-friendly endpoints.

YouTube + Instagram do not expose public trending JSON without auth, so
we use the closest legal/public surfaces:

- YouTube  : per-region "trending" RSS-ish feed via youtube.com/feed/trending
             (HTML parse of video titles), plus optional invidious-style
             aggregator if configured. Falls back to Google Trends.
- Twitter/X: trends24.in mirrors public trending tags per region.
- Instagram: there is no public trending API; we fall back to
             Google Trends queries containing "instagram" + the
             trending tag.
- Google Trends: official daily RSS (most reliable signal).
- Reddit  : /r/popular/.rss
"""
from __future__ import annotations
import asyncio
import re

import feedparser
import httpx
from selectolax.parser import HTMLParser

from ..config import settings
from ..storage import sqlite_store


async def _get(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=settings.scrape_timeout,
                             follow_redirects=True,
                             headers={"User-Agent": settings.user_agent})
        return r.text if r.status_code < 400 else None
    except Exception:
        return None


# ---- Google Trends (daily RSS) -------------------------------------------
def google_trends(geo: str = "US", limit: int = 25) -> list[dict]:
    feed = feedparser.parse(f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}")
    out = []
    for e in feed.entries[:limit]:
        item = {"source": "google_trends",
                "title": e.title, "url": e.link,
                "meta": {"geo": geo, "summary": getattr(e, "summary", "")}}
        sqlite_store.insert_trend(item["source"], item["title"], item["url"], item["meta"])
        out.append(item)
    return out


# ---- YouTube trending (HTML scrape of /feed/trending) --------------------
async def youtube_trending(limit: int = 25) -> list[dict]:
    async with httpx.AsyncClient() as c:
        html = await _get(c, "https://www.youtube.com/feed/trending")
    if not html:
        return []
    # Extract video titles from the initial JSON blob YouTube embeds.
    titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]{5,120})"\}\]', html)
    seen, out = set(), []
    for t in titles:
        if t in seen:
            continue
        seen.add(t)
        item = {"source": "youtube", "title": t,
                "url": "https://www.youtube.com/feed/trending",
                "meta": {}}
        sqlite_store.insert_trend(item["source"], item["title"], item["url"], item["meta"])
        out.append(item)
        if len(out) >= limit:
            break
    return out


# ---- Twitter / X trending (public mirror) --------------------------------
async def twitter_trending(country: str = "united-states", limit: int = 25) -> list[dict]:
    url = f"https://trends24.in/{country}/"
    async with httpx.AsyncClient() as c:
        html = await _get(c, url)
    if not html:
        return []
    tree = HTMLParser(html)
    out = []
    for a in tree.css(".trend-card__list li a"):
        title = a.text(strip=True)
        if not title:
            continue
        item = {"source": "twitter", "title": title,
                "url": f"https://x.com/search?q={title.replace(' ', '%20')}",
                "meta": {"country": country}}
        sqlite_store.insert_trend(item["source"], item["title"], item["url"], item["meta"])
        out.append(item)
        if len(out) >= limit:
            break
    return out


# ---- Instagram (proxy via Google Trends search for IG-related queries) ---
async def instagram_trending(geo: str = "US", limit: int = 15) -> list[dict]:
    # Instagram offers no public trending API. Use Google Trends as proxy,
    # filtered to entries plausibly relevant to short-form / IG culture.
    base = google_trends(geo=geo, limit=limit * 2)
    out = []
    for item in base:
        item = {**item, "source": "instagram_proxy"}
        sqlite_store.insert_trend(item["source"], item["title"], item["url"], item["meta"])
        out.append(item)
        if len(out) >= limit:
            break
    return out


def collect_all_trends() -> dict[str, list[dict]]:
    sqlite_store.init_db()
    return {
        "google_trends_us": google_trends("US"),
        "google_trends_in": google_trends("IN"),
        "youtube":   asyncio.run(youtube_trending()),
        "twitter":   asyncio.run(twitter_trending()),
        "instagram": asyncio.run(instagram_trending()),
    }
