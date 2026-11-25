"""In-process pub/sub message bus.

Every send is mirrored into SQLite (`agent_messages`) so the UI can
replay the conversation and so long-term audits are possible.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Callable

from ..storage import sqlite_store


_subs: dict[str, list[Callable[[dict], None]]] = defaultdict(list)


def subscribe(agent_name: str, handler: Callable[[dict], None]) -> None:
    _subs[agent_name].append(handler)


def send(sender: str, receiver: str, topic: str, body: str) -> None:
    sqlite_store.log_message(sender, receiver, topic, body)
    msg = {"sender": sender, "receiver": receiver, "topic": topic, "body": body}
    for h in _subs.get(receiver, []):
        h(msg)
    for h in _subs.get("*", []):
        h(msg)


def broadcast(sender: str, topic: str, body: str) -> None:
    for name in list(_subs):
        if name in ("*", sender):
            continue
        send(sender, name, topic, body)
