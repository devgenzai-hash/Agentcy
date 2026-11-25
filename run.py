"""Command-line entry point.

Examples:
  python run.py init                       # create DB + seed websites
  python run.py categorize                 # AI-classify all websites
  python run.py scrape news_global         # scrape one field
  python run.py scrape-all                 # scrape every field in chunks
  python run.py trends                     # collect YouTube/Twitter/IG/GTrends
  python run.py index                      # push scraped pages into vector DB
  python run.py ask "viral hooks for AI tools"
  python run.py agency "Find a viral video idea in personal finance"
"""
from __future__ import annotations
import sys

from src.storage import sqlite_store
from src.scrape import scraper
from src.agency import orchestrator
from src.rag import answer, ingest_recent_pages


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    cmd, *rest = argv[1:]

    if cmd == "init":
        sqlite_store.init_db()
        print(orchestrator.bootstrap_websites())
    elif cmd == "categorize":
        print(orchestrator.categorize_websites())
    elif cmd == "scrape":
        field = rest[0]
        print(orchestrator.scrape_field(field))
    elif cmd == "scrape-all":
        results = scraper.scrape_all_chunked(chunk_size=10)
        print({"pages": len(results)})
    elif cmd == "trends":
        out = orchestrator.collect_trends()
        for k, v in out.items():
            print(f"{k}: {len(v)} items")
    elif cmd == "index":
        n = ingest_recent_pages(limit=500)
        print({"chunks_indexed": n})
    elif cmd == "ask":
        q = " ".join(rest)
        print(answer(q)["answer"])
    elif cmd == "agency":
        goal = " ".join(rest)
        out = orchestrator.run_agency(goal)
        print("\n=== FINAL ===\n")
        print(out["final"])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
