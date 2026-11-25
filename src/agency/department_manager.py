"""Department manager: owns a field, can spawn FieldWorkers under it."""
from __future__ import annotations
from .base_agent import Agent
from .worker_agents import FieldWorker


class DepartmentManager(Agent):
    def __init__(self, name: str, field: str, goal: str, parent: str):
        super().__init__(
            name=name,
            role=f"Department manager for `{field}`",
            goal=goal,
            parent=parent,
        )
        self.field = field
        self.workers: list[FieldWorker] = []

    def hire_worker(self, goal: str) -> FieldWorker:
        w = FieldWorker(
            name=Agent.fresh_name(f"{self.field}-worker"),
            field=self.field, goal=goal, parent=self.name,
        )
        self.workers.append(w)
        self.send(w.name, "assignment", goal)
        return w

    def run_brief(self, brief: str, *, workers: int = 2) -> dict:
        # Ensure we have N workers
        while len(self.workers) < workers:
            self.hire_worker(goal=f"Support: {brief}")
        findings = []
        for w in self.workers[:workers]:
            r = w.investigate(brief)
            findings.append({"worker": w.name, "report": r})
            w.send(self.name, "report", r)
        summary = self.think(
            f"Brief: {brief}\n\nWorker reports:\n" +
            "\n\n".join(f"### {f['worker']}\n{f['report']}" for f in findings) +
            "\n\nSynthesise into a single department recommendation.",
            use_rag=False,
        )
        self.remember("decision", summary)
        return {"summary": summary, "findings": findings}
