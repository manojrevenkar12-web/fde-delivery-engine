"""Field to product: custom work that keeps coming back becomes a reusable template, and the hours it saves are counted."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternLibrary:
    template_after: int
    saving_share: float
    work_hours: dict[str, int]
    seen: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    templates: set[str] = field(default_factory=set)
    queued: list[str] = field(default_factory=list)

    @staticmethod
    def from_config(product: dict[str, Any], catalog: dict[str, Any]) -> "PatternLibrary":
        return PatternLibrary(product["patterns"]["templateAfterEngagements"], catalog["templateSavingShare"],
                              {k: v["hours"] for k, v in catalog["workTypes"].items()})

    def record(self, engagement_id: str, work_items: tuple[str, ...]) -> None:
        """Counts custom work as an engagement starts its build; queues a template once a type recurs enough."""
        for item in work_items:
            if item in self.templates:
                continue
            self.seen[item].add(engagement_id)
            if len(self.seen[item]) >= self.template_after and item not in self.queued:
                self.queued.append(item)

    def built(self, item: str) -> None:
        if item in self.queued:
            self.queued.remove(item)
        self.templates.add(item)

    def build_hours(self, work_items: tuple[str, ...]) -> float:
        """The build hours these work items need, after templates."""
        total = 0.0
        for item in work_items:
            hours = self.work_hours[item]
            total += hours * (1 - self.saving_share) if item in self.templates else hours
        return total

    def product_requests(self) -> list[dict[str, Any]]:
        """Recurring custom work, most frequent first: the field insight that goes to Product and Engineering."""
        rows = [{"workType": k, "engagements": len(v), "templated": k in self.templates}
                for k, v in self.seen.items()]
        return sorted(rows, key=lambda r: (-r["engagements"], r["workType"]))
