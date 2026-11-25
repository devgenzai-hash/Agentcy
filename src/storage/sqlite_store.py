"""SQLite store for raw scraped pages, agent messages, and HITL log.

`pages.body_html` keeps the original tags as the user requested
(tags-as-identifiers). `pages.text` is the cleaned plain text used
for embedding / RAG.
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from ..config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS websites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT UNIQUE NOT NULL,
    domain      TEXT,
    category    TEXT,           -- AI-assigned field
    field       TEXT,           -- coarse bucket (news, tech, marketing, social-trends...)
    notes       TEXT,
    created_at  REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id  INTEGER REFERENCES websites(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    title       TEXT,
    body_html   TEXT,           -- tag-preserved snippets
    text        TEXT,           -- cleaned text
    tags_json   TEXT,           -- {"h1":[...], "h2":[...], "a":[...], ...}
    fetched_at  REAL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);

CREATE TABLE IF NOT EXISTS trending (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT,           -- youtube | twitter | instagram | ...
    title       TEXT,
    url         TEXT,
    meta_json   TEXT,
    fetched_at  REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender      TEXT,
    receiver    TEXT,
    topic       TEXT,
    body        TEXT,
    ts          REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS memory_long (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT,
    kind        TEXT,           -- fact | insight | decision
    content     TEXT,
    ts          REAL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS hitl_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT,
    question    TEXT,
    answer      TEXT,
    approved    INTEGER,
    ts          REAL DEFAULT (strftime('%s','now'))
);
"""


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    _ensure_dir(settings.sqlite_path)
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


# ---------- websites ----------
def upsert_website(url: str, domain: str, field: str, category: str = "", notes: str = "") -> int:
    with connect() as c:
        c.execute(
            "INSERT INTO websites(url, domain, field, category, notes) VALUES (?,?,?,?,?) "
            "ON CONFLICT(url) DO UPDATE SET field=excluded.field, category=excluded.category, "
            "notes=excluded.notes",
            (url, domain, field, category, notes),
        )
        row = c.execute("SELECT id FROM websites WHERE url=?", (url,)).fetchone()
        return row["id"]


def list_websites(field: str | None = None) -> list[dict]:
    with connect() as c:
        if field:
            rows = c.execute("SELECT * FROM websites WHERE field=? ORDER BY domain", (field,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM websites ORDER BY field, domain").fetchall()
        return [dict(r) for r in rows]


def fields() -> list[str]:
    with connect() as c:
        rows = c.execute("SELECT DISTINCT field FROM websites WHERE field IS NOT NULL").fetchall()
        return [r["field"] for r in rows]


# ---------- pages ----------
def insert_page(website_id: int | None, url: str, title: str,
                body_html: str, text: str, tags: dict) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO pages(website_id, url, title, body_html, text, tags_json) "
            "VALUES (?,?,?,?,?,?)",
            (website_id, url, title, body_html, text, json.dumps(tags, ensure_ascii=False)),
        )
        return cur.lastrowid


def recent_pages(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT id, url, title, fetched_at FROM pages ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_page(page_id: int) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
        return dict(r) if r else None


# ---------- trending ----------
def insert_trend(source: str, title: str, url: str, meta: dict) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO trending(source, title, url, meta_json) VALUES (?,?,?,?)",
            (source, title, url, json.dumps(meta, ensure_ascii=False)),
        )


def recent_trends(source: str | None = None, limit: int = 50) -> list[dict]:
    with connect() as c:
        if source:
            rows = c.execute(
                "SELECT * FROM trending WHERE source=? ORDER BY fetched_at DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM trending ORDER BY fetched_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# ---------- agent messages / memory / HITL ----------
def log_message(sender: str, receiver: str, topic: str, body: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO agent_messages(sender, receiver, topic, body) VALUES (?,?,?,?)",
            (sender, receiver, topic, body),
        )


def recent_messages(limit: int = 100) -> list[dict]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM agent_messages ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def remember(agent: str, kind: str, content: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO memory_long(agent, kind, content) VALUES (?,?,?)",
            (agent, kind, content),
        )


def recall(agent: str | None = None, limit: int = 50) -> list[dict]:
    with connect() as c:
        if agent:
            rows = c.execute(
                "SELECT * FROM memory_long WHERE agent=? ORDER BY ts DESC LIMIT ?",
                (agent, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM memory_long ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def log_hitl(agent: str, question: str, answer: str, approved: bool) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO hitl_log(agent, question, answer, approved) VALUES (?,?,?,?)",
            (agent, question, answer, int(approved)),
        )
