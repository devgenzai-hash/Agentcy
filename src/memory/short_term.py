"""Per-agent rolling short-term memory (in-process, bounded)."""
from __future__ import annotations
from collections import defaultdict, deque

_BUFS: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=20))


def push(agent: str, role: str, content: str) -> None:
    _BUFS[agent].append({"role": role, "content": content})


def history(agent: str) -> list[dict]:
    return list(_BUFS[agent])


def clear(agent: str) -> None:
    _BUFS[agent].clear()
