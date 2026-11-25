"""High-level orchestration: bootstrap the knowledge base, then run the agency."""
from __future__ import annotations

from ..scrape import seeds, categorizer, scraper, trends
from ..storage import sqlite_store, vector_store
from ..rag import chunker
from .lead_manager import LeadManager


# ---------- knowledge bootstrap -----------------------------------------
def bootstrap_websites() -> dict:
    n = seeds.ingest_seed()
    return {"seeded": n}


def categorize_websites() -> dict:
    m = categorizer.categorize_all()
    return {"categorized": len(m)}


def scrape_field(field: str) -> dict:
    results = scraper.scrape_field(field)
    return {"field": field, "pages": len(results), "results": results}


def collect_trends() -> dict:
    return trends.collect_all_trends()


def index_pages_into_vector(field: str | None = None) -> int:
    pages = sqlite_store.list_websites(field=field) if field else None
    page_rows = sqlite_store.recent_pages(limit=10_000)
    if field:
        allowed = {p["url"] for p in (pages or [])}
        page_rows = [p for p in page_rows if any(p["url"].startswith(u.split("?")[0]) or p["url"] == u for u in allowed)]
    total = 0
    for p in page_rows:
        page = sqlite_store.get_page(p["id"])
        if not page:
            continue
        chunks = chunker.chunk_tagged(page["body_html"] or page["text"] or "")
        if not chunks:
            continue
        site_field = field or _resolve_field(page["url"])
        metas = [{
            "source": "page", "page_id": p["id"],
            "url": page["url"], "title": page["title"],
            "field": site_field or "unknown",
        } for _ in chunks]
        vector_store.add_documents(chunks, metas)
        total += len(chunks)
    return total


def _resolve_field(url: str) -> str | None:
    for w in sqlite_store.list_websites():
        if w["url"] == url:
            return w["field"]
    return None


# ---------- agency entrypoint -------------------------------------------
def run_agency(goal: str, *, workers_per_dept: int = 2) -> dict:
    lead = LeadManager(goal=goal)
    return lead.execute(goal, workers_per_dept=workers_per_dept)
