"""Intake: can the team take this engagement on and still deliver what it already promised?

The forecast spreads the remaining work of every live engagement, and the candidate's scope, evenly up to their due
dates, then compares each profile's average load over the next weeks with what that profile can deliver at the utilization target. Adjacent
profiles count for their share. Saying no is a commercial decision too, so the answer carries the numbers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fde.product.model import PHASES, PROFILE_OF_PHASE, Engagement, EngagementState, Fde


@dataclass(frozen=True)
class IntakeDecision:
    accept: bool
    reason: str
    load_by_profile: dict[str, float]


def _spread(load: dict[tuple[str, int], float], profile: str, hours: float, start: int, end: int) -> None:
    weeks = max(1, end - start)
    for w in range(start, start + weeks):
        load[(profile, w)] += hours / weeks


def decide(week: int, candidate: Engagement, states: list[EngagementState], roster: list[Fde],
           catalog: dict[str, Any], product: dict[str, Any]) -> IntakeDecision:
    s = product["intake"]
    horizon = s["horizonWeeks"]
    target = product["staffing"]["utilizationTarget"] * s["maxLoadOfTarget"]
    load: dict[tuple[str, int], float] = defaultdict(float)
    for st in states:
        if st.done:
            continue
        start = week
        for phase in PHASES[PHASES.index(st.phase):]:
            hours = st.remaining_estimate(phase) if phase == st.phase else st.engagement.phases[phase].scoped_hours
            end = max(start + 1, st.due(phase))
            _spread(load, PROFILE_OF_PHASE[phase], hours, start, end)
            start = end
    start = week
    for phase in PHASES:
        end = max(start + 1, candidate.phases[phase].due_week)
        _spread(load, PROFILE_OF_PHASE[phase], candidate.phases[phase].scoped_hours, start, end)
        start = end
    capacity: dict[str, float] = defaultdict(float)
    for f in roster:
        capacity[f.profile] += f.capacity_hours * target
    adjacent = {k: v for k, v in catalog["adjacentProfiles"].items() if not k.startswith("_")}
    peak: dict[str, float] = {}
    for profile in capacity:
        cover = capacity[profile] + sum(capacity[o] * share * s["adjacentCoverShare"]
                                        for o, share in adjacent.get(profile, {}).items())
        weekly = [load[(profile, w)] for w in range(week, week + horizon)]
        # The average over the horizon, not the peak: a one-week spike is what staffing absorbs.
        peak[profile] = round(sum(weekly) / len(weekly) / max(1.0, cover), 3)
    worst = max(peak, key=lambda p: peak[p])
    if peak[worst] > 1.0:
        return IntakeDecision(False, f"{worst} would run at {peak[worst]:.0%} of what it can deliver", peak)
    return IntakeDecision(True, f"fits: busiest profile {worst} at {peak[worst]:.0%}", peak)
