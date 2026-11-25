"""Lead Manager (the "agency owner").

Receives the top-level goal, asks the human for clarifications via the
HITL gate, picks which departments to involve, dispatches briefs to
them, and synthesises a final deliverable.
"""
from __future__ import annotations
import json

from .base_agent import Agent
from .department_manager import DepartmentManager
from ..storage import sqlite_store


PLAN_SYS = (
    "You are the lead manager of a creative social-media agency. "
    "Given a goal, choose 1-3 relevant fields from this allowed list and write a brief for each. "
    "Return strict JSON: {\"plan\":[{\"field\":\"...\",\"brief\":\"...\"}]}"
)


class LeadManager(Agent):
    def __init__(self, name: str = "lead-manager", goal: str = ""):
        super().__init__(name=name, role="Lead manager / agency owner", goal=goal)
        self.departments: dict[str, DepartmentManager] = {}

    def _ensure_department(self, field: str) -> DepartmentManager:
        if field not in self.departments:
            dm = DepartmentManager(
                name=f"dept-{field}",
                field=field,
                goal=f"Own the `{field}` knowledge area for the agency.",
                parent=self.name,
            )
            self.departments[field] = dm
        return self.departments[field]

    def plan(self, goal: str) -> list[dict]:
        allowed = sorted({s["field"] for s in sqlite_store.list_websites()})
        raw = self.think(
            f"Goal: {goal}\n\nAllowed fields: {allowed}\n\n" + PLAN_SYS,
            use_rag=False,
        )
        try:
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            plan = data.get("plan", [])
        except Exception:
            plan = [{"field": allowed[0] if allowed else "news_global", "brief": goal}]
        return [p for p in plan if p.get("field") in allowed] or plan

    def execute(self, goal: str, *, workers_per_dept: int = 2) -> dict:
        # Optional HITL: clarify goal before spending tokens
        clarif = self.ask_human(f"Goal received: '{goal}'. Any constraints?")
        if clarif:
            goal = f"{goal}\nUser constraints: {clarif}"

        plan = self.plan(goal)
        results = []
        for step in plan:
            dm = self._ensure_department(step["field"])
            res = dm.run_brief(step["brief"], workers=workers_per_dept)
            results.append({"field": step["field"], **res})

        synthesis = self.think(
            f"Original goal: {goal}\n\nDepartment outputs:\n" +
            "\n\n".join(f"## {r['field']}\n{r['summary']}" for r in results) +
            "\n\nProduce the final agency deliverable: viral video ideas, hooks, "
            "captions, and rationale. Cite which field each idea came from.",
            use_rag=False,
        )
        self.remember("decision", synthesis)
        return {"goal": goal, "plan": plan, "results": results, "final": synthesis}
