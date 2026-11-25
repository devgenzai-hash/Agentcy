"""Worker agents specialised by field. Each one is grounded in a
particular `field` bucket (news, tech, marketing_creative, ...). They
pull RAG context restricted to their field and report findings up to
their department manager.
"""
from __future__ import annotations
from .base_agent import Agent
from ..storage import vector_store


class FieldWorker(Agent):
    """A worker specialised on one field bucket (e.g. 'tech_news')."""

    def __init__(self, name: str, field: str, goal: str, parent: str):
        super().__init__(
            name=name,
            role=f"Field researcher specialised in `{field}`",
            goal=goal,
            parent=parent,
        )
        self.field = field

    def search_field(self, query: str, k: int = 8) -> list[dict]:
        # When pages are ingested we tag them with their field via metadata
        # in the orchestrator, so restrict retrieval to that bucket.
        return vector_store.query(query, k=k, where={"field": self.field})

    def investigate(self, query: str) -> str:
        hits = self.search_field(query)
        bullets = "\n".join(f"- ({h['metadata'].get('url','?')}) {h['document'][:300]}"
                            for h in hits[:6])
        prompt = (f"Investigate this question for your field `{self.field}`:\n{query}\n\n"
                  f"Snippets from your field's corpus:\n{bullets}\n\n"
                  "Produce: (1) 3 key insights, (2) 3 viral angles, (3) sources used.")
        return self.think(prompt, use_rag=False)
