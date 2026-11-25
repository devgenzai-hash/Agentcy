"""Base agent class.

Each agent has:
- a unique name + role description (the "system prompt")
- short-term + long-term memory access
- a RAG-grounded `think()` method that always queries the indexed corpus
- ability to send messages to other agents via the bus
- ability to ask a human via the HITL gate
- ability to spawn worker agents (only managers do this in practice)
"""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field

from ..llm import system_user
from ..memory import short_term, long_term
from ..rag import answer as rag_answer
from ..hitl import ask as ask_human
from . import message_bus


@dataclass
class Agent:
    name: str
    role: str
    goal: str = ""
    parent: str | None = None
    inbox: list[dict] = field(default_factory=list)

    # ---------------- lifecycle ------------------------------------------
    def __post_init__(self):
        message_bus.subscribe(self.name, self.inbox.append)

    # ---------------- core thinking --------------------------------------
    def _system_prompt(self) -> str:
        return (
            f"You are {self.name}, role: {self.role}.\n"
            f"Goal: {self.goal or '(no specific goal yet)'}\n"
            "You work inside a creative social-media agency of cooperating AI agents. "
            "Be concise, decisive, and cite sources when you use retrieved context."
        )

    def think(self, task: str, *, use_rag: bool = True) -> str:
        short_term.push(self.name, "user", task)
        context = ""
        if use_rag:
            rag = rag_answer(task, top_k=4)
            context = f"\n\nGrounded context:\n{rag['answer']}"
        prompt = task + context + "\n\nRecent memory:\n" + json.dumps(
            short_term.history(self.name)[-6:], ensure_ascii=False)
        out = system_user(self._system_prompt(), prompt, temperature=0.4, max_tokens=700)
        short_term.push(self.name, "assistant", out)
        return out

    # ---------------- collaboration --------------------------------------
    def send(self, receiver: str, topic: str, body: str) -> None:
        message_bus.send(self.name, receiver, topic, body)

    def ask_human(self, question: str) -> str:
        return ask_human(self.name, question)

    def remember(self, kind: str, content: str) -> None:
        long_term.remember(self.name, kind, content)

    # ---------------- hierarchy ------------------------------------------
    def spawn(self, name: str, role: str, goal: str) -> "Agent":
        child = Agent(name=name, role=role, goal=goal, parent=self.name)
        self.send(receiver=name, topic="spawn",
                  body=f"You have been spawned by {self.name} with goal: {goal}")
        return child

    # ---------------- helpers --------------------------------------------
    @staticmethod
    def fresh_name(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:6]}"
