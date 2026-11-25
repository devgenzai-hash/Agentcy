"""Load curated websites + ask the LLM to refine category buckets."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

from ..storage import sqlite_store

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "websites.json"


def load_seed() -> dict[str, list[str]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def ingest_seed() -> int:
    """Insert all seed sites into the websites table with their field bucket."""
    sqlite_store.init_db()
    data = load_seed()
    n = 0
    for field, urls in data.items():
        for url in urls:
            domain = urlparse(url).netloc
            sqlite_store.upsert_website(url=url, domain=domain, field=field)
            n += 1
    return n
