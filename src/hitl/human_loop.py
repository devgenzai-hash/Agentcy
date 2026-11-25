"""Human-in-the-loop gate.

Agents call `ask()` whenever they need approval, clarification, or
extra context. By default we register a CLI prompter; the Streamlit UI
swaps in a queue-backed handler so questions surface in the web UI.
"""
from __future__ import annotations
from typing import Callable

from ..config import settings
from ..storage import sqlite_store


_handler: Callable[[str, str], str] | None = None


def set_handler(fn: Callable[[str, str], str]) -> None:
    """fn(agent_name, question) -> human's answer (empty string = auto-approve)."""
    global _handler
    _handler = fn


def _cli_handler(agent: str, question: str) -> str:
    print(f"\n[HITL] {agent} asks: {question}")
    return input("Your input (blank=approve): ").strip()


def ask(agent: str, question: str, *, auto_approve_if_disabled: bool = True) -> str:
    if not settings.human_in_the_loop:
        if auto_approve_if_disabled:
            sqlite_store.log_hitl(agent, question, "(auto-approved)", True)
            return ""
    fn = _handler or _cli_handler
    answer = fn(agent, question)
    sqlite_store.log_hitl(agent, question, answer, approved=True)
    return answer
