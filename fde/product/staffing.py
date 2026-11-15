"""Weekly staffing: the right FDE profile on the right engagement, inside the utilization band, never hot two weeks running.

The planner sees what a delivery manager sees: scopes, due dates, logged hours, the team's own progress reports,
who is out this week and who ran hot last week. It plans in day-sized blocks.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fde.product.model import PROFILE_OF_PHASE, Assignment, EngagementState, Fde, Plan


@dataclass(frozen=True)
class StaffingSettings:
    utilization_target: float
    utilization_floor: float
    hot_load: float
    max_hot_weeks_in_a_row: int
    block_hours: int
    ramp_up: float
    skill_gap: float
    min_effective_rate: float
    skill_mismatch_allowed: bool
    escalated_priority_boost: float
    finish_weeks_early: int = 1
    safety_factor: float = 1.25

    @staticmethod
    def from_config(product: dict[str, Any]) -> "StaffingSettings":
        s = product["staffing"]
        return StaffingSettings(s["utilizationTarget"], s["utilizationFloor"], s["hotLoad"], s["maxHotWeeksInARow"],
                                s["blockHours"], s["assumedRampUp"], s["assumedSkillGap"], s["minEffectiveRate"],
                                s["skillMismatchAllowed"],
                                s["escalatedPriorityBoost"], s["finishWeeksEarly"], s["safetyFactor"])


@dataclass
class _Demand:
    state: EngagementState
    phase: str
    profile: str
    need: float
    forward: float
    priority: float
    weeks_left: int


def _floor_block(hours: float, block: int) -> int:
    return int(hours // block) * block


def plan_week(week: int, roster: list[Fde], available: dict[str, int], states: list[EngagementState],
              last_plan: Plan | None, hot_streak: dict[str, int], template_tasks: list[str],
              settings: StaffingSettings, catalog: dict[str, Any]) -> Plan:
    block = settings.block_hours
    adjacent: dict[str, dict[str, float]] = {k: v for k, v in catalog["adjacentProfiles"].items()
                                             if not k.startswith("_")}
    load: dict[str, int] = defaultdict(int)
    limit = {f.id: _floor_block(available.get(f.id, 0) * settings.utilization_target, block) for f in roster}
    # A stretch week is a full week, never overtime, and never two in a row.
    stretch = {f.id: (_floor_block(available.get(f.id, 0), block)
                      if hot_streak.get(f.id, 0) < settings.max_hot_weeks_in_a_row else limit[f.id]) for f in roster}
    floor = {f.id: available.get(f.id, 0) * settings.utilization_floor for f in roster}
    previous = {(a.fde_id, a.engagement_id) for a in (last_plan.assignments if last_plan else [])}
    hours: dict[tuple[str, str, str], int] = defaultdict(int)
    warnings: list[str] = []

    demands: list[_Demand] = []
    for st in states:
        if st.done or st.engagement.start_week > week:
            continue
        remaining = st.remaining_estimate(st.phase)
        if remaining <= 0:
            continue
        weeks_left = max(1, st.due(st.phase) - week)
        # Aim to finish before the due date, with a safety margin for ramp-up and overruns the scope cannot see.
        aim = max(1, weeks_left - settings.finish_weeks_early)
        overdue = week - st.due(st.phase)
        if overdue >= 0:
            need = remaining  # the date is gone: finish it, without a margin that would starve the next one
        else:
            need = min(remaining * settings.safety_factor,
                       math.ceil(remaining * settings.safety_factor / aim / block) * block)
        # Due soon goes first; overdue work climbs a week at a time, so nothing waits forever behind newer work.
        priority = 1.0 / weeks_left if overdue < 0 else 1.0 + overdue
        if st.escalated_week is not None and week - st.escalated_week <= 4:
            priority *= settings.escalated_priority_boost
        demands.append(_Demand(st, st.phase, PROFILE_OF_PHASE[st.phase], need, max(0.0, remaining - need), priority,
                               weeks_left if overdue < 0 else 0))
    demands.sort(key=lambda d: (-d.priority, d.state.engagement.id))

    def fit(f: Fde, profile: str) -> float:
        if f.profile == profile:
            return 1.0
        return adjacent.get(profile, {}).get(f.profile, 0.0)

    def rate(f: Fde, d: _Demand) -> float:
        """Expected effective output per hour: profile fit, skill coverage, ramp-up for someone new."""
        r = fit(f, d.profile)
        if not d.state.engagement.required_skills <= f.skills:
            r *= 0.0 if settings.skill_mismatch_allowed is None else settings.skill_gap
        if (f.id, d.state.engagement.id) not in previous:
            r *= settings.ramp_up
        return r

    def assign(d: _Demand, amount: float, cap: dict[str, int], floor_rate: float) -> float:
        """Places `amount` effective hours on the people who turn hours into progress best; returns what is left."""
        while amount > 0:
            best: tuple[float, float, str, Fde] | None = None
            for f in roster:
                if load[f.id] + block > cap[f.id]:
                    continue
                r = rate(f, d)
                if r < floor_rate or r <= 0:
                    continue
                key = (r, -load[f.id] / max(1, available.get(f.id, 0)), f.id)
                if best is None or key[:2] > best[:2] or (key[:2] == best[:2] and f.id < best[2]):
                    best = (key[0], key[1], f.id, f)
            if best is None:
                return amount
            f, r = best[3], best[0]
            # Give one person as much of the need as they can take: every new pairing pays a ramp-up.
            room = _floor_block(cap[f.id] - load[f.id], block)
            take = min(room, math.ceil(amount / r / block) * block)
            load[f.id] += take
            hours[(f.id, d.state.engagement.id, d.phase)] += take
            amount -= take * r
        return 0.0

    for d in demands:
        short = assign(d, d.need, limit, settings.min_effective_rate)
        at_stake = d.weeks_left == 1  # due next week and still savable; overdue work (0) does not qualify
        if short > 0 and at_stake:
            # A date is at stake: stretch people who were not hot last week, then take weaker matches.
            short = assign(d, short, stretch, settings.min_effective_rate)
            before = short
            short = assign(d, short, stretch, 0.01)
            if short < before:
                warnings.append(f"{d.state.engagement.id} covered by weaker matches to hold its date")
        if short > 0:
            warnings.append(f"{d.state.engagement.id} is short {math.ceil(short)}h of {d.profile} for {d.phase}")

    # Below the floor: build templates first (they pay back on every later engagement), then pull work forward.
    for task in template_tasks:
        builders = sorted((f for f in roster if f.profile == "builder" and load[f.id] < floor[f.id]),
                          key=lambda f: (load[f.id], f.id))
        if builders:
            f = builders[0]
            add = min(int(catalog["templateBuildHours"]), max(0, limit[f.id] - load[f.id]))
            add = _floor_block(add, block)
            if add > 0:
                load[f.id] += add
                hours[(f.id, "template:" + task, "build")] += add
    for d in demands:
        if d.forward <= 0:
            continue
        for f in sorted(roster, key=lambda x: (-rate(x, d), load[x.id], x.id)):
            if d.forward <= 0:
                break
            if rate(f, d) < settings.min_effective_rate or load[f.id] >= floor[f.id]:
                continue
            add = _floor_block(min(d.forward, floor[f.id] - load[f.id] + block, limit[f.id] - load[f.id]), block)
            if add > 0:
                load[f.id] += add
                hours[(f.id, d.state.engagement.id, d.phase)] += add
                d.forward -= add * rate(f, d)

    assignments = [Assignment(f, e, p, h) for (f, e, p), h in sorted(hours.items()) if h > 0]
    return Plan(week, assignments, warnings)


def hot_streaks(plan: Plan, available: dict[str, int], previous: dict[str, int], hot_load: float) -> dict[str, int]:
    """Weeks in a row each FDE was planned above the hot line; the planner keeps this to protect people."""
    out: dict[str, int] = {}
    for fde_id, cap in available.items():
        hot = cap > 0 and plan.hours_of(fde_id) > cap * hot_load - 1e-9
        out[fde_id] = previous.get(fde_id, 0) + 1 if hot else 0
    return out
