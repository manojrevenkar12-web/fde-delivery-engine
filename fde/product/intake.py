"""Intake: can the team take this engagement on and still deliver what it already promised?

The forecast spreads the remaining work of every live engagement, and the candidate's scope, evenly up to their due
dates. Work that needs a skill (German, clearance) can only go to people who have it, so the check is made for every
skill set the work asks for: the average load over the next weeks of work needing at least that set, against what
the people who have that set can deliver at the utilization target. Adjacent profiles with the skills count for
their share. Saying no is a commercial decision too, so the answer carries the numbers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fde.product.model import PHASES, PROFILE_OF_PHASE, Engagement, EngagementState, Fde

Key = tuple[str, frozenset[str]]


@dataclass(frozen=True)
class IntakeDecision:
    accept: bool
    reason: str
    load_by_profile: dict[str, float]


def _spread(load: dict[tuple[Key, int], float], key: Key, hours: float, start: int, end: int) -> None:
    weeks = max(1, end - start)
    for w in range(start, start + weeks):
        load[(key, w)] += hours / weeks


def _label(profile: str, skills: frozenset[str]) -> str:
    return profile if not skills else f"{profile} with {' and '.join(sorted(skills))}"


def decide(week: int, candidate: Engagement, states: list[EngagementState], roster: list[Fde],
           catalog: dict[str, Any], product: dict[str, Any]) -> IntakeDecision:
    s = product["intake"]
    horizon = s["horizonWeeks"]
    target = product["staffing"]["utilizationTarget"] * s["maxLoadOfTarget"]
    load: dict[tuple[Key, int], float] = defaultdict(float)
    for st in states:
        if st.done:
            continue
        start = week
        need = frozenset(st.engagement.required_skills)
        for phase in PHASES[PHASES.index(st.phase):]:
            hours = st.remaining_estimate(phase) if phase == st.phase else st.engagement.phases[phase].scoped_hours
            end = max(start + 1, st.due(phase))
            _spread(load, (PROFILE_OF_PHASE[phase], need), hours, start, end)
            start = end
    start = week
    need = frozenset(candidate.required_skills)
    for phase in PHASES:
        end = max(start + 1, candidate.phases[phase].due_week)
        _spread(load, (PROFILE_OF_PHASE[phase], need), candidate.phases[phase].scoped_hours, start, end)
        start = end
    gap = product["staffing"]["assumedSkillGap"]
    adjacent = {k: v for k, v in catalog["adjacentProfiles"].items() if not k.startswith("_")}
    profiles = {f.profile for f in roster}
    keys = {k for (k, _) in load} | {(p, frozenset()) for p in profiles}
    ratio: dict[str, float] = {}
    for profile, skills in keys:
        def capacity(p: str) -> float:
            # Someone without the skills still moves the work, at the rate the planner assumes for a skill gap.
            return sum(f.capacity_hours * target * (1.0 if skills <= f.skills else gap) for f in roster
                       if f.profile == p)
        cover = capacity(profile) + sum(capacity(o) * share * s["adjacentCoverShare"]
                                        for o, share in adjacent.get(profile, {}).items())
        # Every piece of work that needs at least these skills competes for the same people.
        weekly = [sum(h for ((p, need_k), wk), h in load.items() if p == profile and skills <= need_k and wk == w)
                  for w in range(week, week + horizon)]
        avg = sum(weekly) / len(weekly)
        if avg == 0:
            continue
        # The average over the horizon, not the peak: a one-week spike is what staffing absorbs.
        ratio[_label(profile, skills)] = round(avg / cover, 3) if cover > 0 else float("inf")
    worst = max(ratio, key=lambda p: ratio[p])
    if ratio[worst] > 1.0:
        shown = "no one" if ratio[worst] == float("inf") else f"{ratio[worst]:.0%} of what they can deliver"
        return IntakeDecision(False, f"{worst} would run at {shown}", ratio)
    return IntakeDecision(True, f"fits: busiest {worst} at {ratio[worst]:.0%}", ratio)
