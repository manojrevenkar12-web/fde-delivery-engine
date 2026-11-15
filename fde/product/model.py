"""What the engine knows about the team and the engagements: scopes, plans, logged hours and status notes, never the truth."""

from __future__ import annotations

from dataclasses import dataclass, field

PHASES = ("discovery", "build", "go_live", "hypercare")
PROFILE_OF_PHASE = {"discovery": "advisory", "build": "builder", "go_live": "operating", "hypercare": "support"}


@dataclass(frozen=True)
class Fde:
    id: str
    name: str
    profile: str
    skills: frozenset[str]
    capacity_hours: int


@dataclass(frozen=True)
class PhaseScope:
    scoped_hours: int
    due_week: int


@dataclass(frozen=True)
class Engagement:
    id: str
    customer: str
    sector: str
    topology: str
    contract: str  # "tm" (time and materials) or "fixed"
    fixed_fee: int
    start_week: int
    phases: dict[str, PhaseScope]
    required_skills: frozenset[str]
    work_items: tuple[str, ...]


@dataclass
class EngagementState:
    """The engine's running view of one engagement."""

    engagement: Engagement
    phase: str
    logged: dict[str, float] = field(default_factory=dict)
    reported_done: dict[str, float] = field(default_factory=dict)
    due_extension: dict[str, int] = field(default_factory=dict)
    escalated_week: int | None = None
    done: bool = False

    def due(self, phase: str) -> int:
        return self.engagement.phases[phase].due_week + self.due_extension.get(phase, 0)

    def remaining_estimate(self, phase: str) -> float:
        """Scoped hours left, re-estimated from the team's own progress report when it says more is left."""
        scoped = self.engagement.phases[phase].scoped_hours
        logged = self.logged.get(phase, 0.0)
        left = max(0.0, scoped - logged)
        pct = self.reported_done.get(phase)
        if pct is not None and 0.05 <= pct < 1.0 and logged > 0:
            left = max(left, logged * (1 - pct) / pct)
        return left


@dataclass(frozen=True)
class Assignment:
    fde_id: str
    engagement_id: str  # an engagement id, or "template:<work type>" for internal template work
    phase: str
    hours: int


@dataclass
class Plan:
    week: int
    assignments: list[Assignment]
    warnings: list[str]

    def hours_of(self, fde_id: str) -> int:
        return sum(a.hours for a in self.assignments if a.fde_id == fde_id)
