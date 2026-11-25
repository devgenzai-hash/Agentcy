"""Token-cheap chunker that respects HTML-tagged storage.

Each scraped page is stored as `<tag>text</tag>` lines. We chunk by
accumulating those lines until ~`max_chars` is reached, preserving the
tag identifier so the agent always knows whether a fact came from an
H1, P, A, etc.
"""
from __future__ import annotations
from typing import Iterable


def chunk_tagged(body_html: str, *, max_chars: int = 1200, overlap_lines: int = 1) -> list[str]:
    lines = [ln.strip() for ln in body_html.splitlines() if ln.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        if size + len(ln) > max_chars and buf:
            chunks.append("\n".join(buf))
            buf = buf[-overlap_lines:] if overlap_lines else []
            size = sum(len(x) for x in buf)
        buf.append(ln)
        size += len(ln)
        i += 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
