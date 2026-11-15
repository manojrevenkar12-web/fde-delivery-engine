"""What happens in a week: work turns into progress at each person's true pace, people tire, blockers and scope creep
appear, milestones are met or slip, and status notes get written."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fde.world.world import PHASES, PROFILE_OF_PHASE, Blocker, Job, World


@dataclass
class WeekLog:
    logged: dict[tuple[str, str], float] = field(default_factory=dict)  # (job, phase) -> hours
    phase_done: list[tuple[str, str]] = field(default_factory=list)
    gate_due: list[str] = field(default_factory=list)
    slips: list[tuple[str, str]] = field(default_factory=list)
    hours_by_person: dict[str, float] = field(default_factory=dict)
    template_hours: dict[str, float] = field(default_factory=dict)


def available(w: World, week: int) -> dict[str, int]:
    return {p.id: (0 if p.sick_until >= week else p.capacity) for p in w.people}


def active_jobs(w: World, week: int) -> list[Job]:
    return [j for j in w.jobs if j.accepted and j.start_week <= week and not j.finished]


def _fit(w: World, person_profile: str, phase: str) -> float:
    need = PROFILE_OF_PHASE[phase]
    if person_profile == need:
        return 1.0
    return w.catalog["adjacentProfiles"].get(need, {}).get(person_profile, 0.0)


def work(w: World, week: int, assignments: list[tuple[str, str, str, float]]) -> WeekLog:
    """Applies a week's assignments: (person, job id or 'template:<type>', phase, hours)."""
    ppl = w.cfg["people"]
    log = WeekLog()
    jobs = {j.id: j for j in w.jobs}
    for pid, target, phase, hours in assignments:
        person = w.person(pid)
        if hours <= 0 or person.sick_until >= week:
            continue
        log.hours_by_person[pid] = log.hours_by_person.get(pid, 0.0) + hours
        if target.startswith("template:"):
            item = target.split(":", 1)[1]
            log.template_hours[item] = log.template_hours.get(item, 0.0) + hours
            continue
        job = jobs[target]
        if job.finished or job.phase != phase or job.start_week > week:
            continue
        log.logged[(job.id, phase)] = log.logged.get((job.id, phase), 0.0) + hours
        rate = person.productivity * _fit(w, person.profile, phase)
        if pid not in job.team_on:
            rate *= ppl["newToEngagementProductivity"]
        if not job.required <= person.skills:
            rate *= ppl["skillMismatchProductivity"]
        rate *= max(0.3, 1 - ppl["fatigueProductivityLoss"] * person.fatigue)
        if job.blocker is not None and phase != "hypercare":
            rate *= w.cfg["risks"]["blockedProgressShare"]
        job.progress[phase] += hours * rate
    for job in jobs.values():
        for pid, _target, phase, hours in assignments:
            if _target == job.id and hours > 0:
                job.team_on.add(pid)
    for job in active_jobs(w, week):
        while not job.finished and job.progress[job.phase] >= job.true_hours[job.phase] and not job.gate_due:
            job.done_week[job.phase] = week
            log.phase_done.append((job.id, job.phase))
            i = PHASES.index(job.phase)
            if i == len(PHASES) - 1:
                job.finished = True
                break
            if job.phase == "build":
                job.gate_due = True
                log.gate_due.append(job.id)
            job.phase = PHASES[i + 1]
    _fatigue(w, week, log)
    return log


def _fatigue(w: World, week: int, log: WeekLog) -> None:
    ppl = w.cfg["people"]
    for p in w.people:
        load = log.hours_by_person.get(p.id, 0.0) / p.capacity
        if load > ppl["hotLoad"] + 1e-9:
            p.fatigue += ppl["fatiguePerHotWeek"]
        else:
            p.fatigue = max(0, p.fatigue - 1)
        if p.fatigue >= 3 and w.k.chance(ppl["sickChanceAtFatigue3"], "sick", p.id, week):
            p.sick_until = week + 1
            p.fatigue = 1


def events(w: World, week: int) -> None:
    """Blockers start and end, and customers ask for more."""
    r = w.cfg["risks"]
    for job in active_jobs(w, week):
        if job.blocker is not None and week >= job.blocker.started + job.blocker.weeks:
            job.blocker = None
        if job.blocker is None and job.phase != "hypercare" and w.k.chance(r["blockerPerWeek"], "blocker", job.id, week):
            weeks = w.k.between(r["blockerWeeksMin"], r["blockerWeeksMax"], "blockerWeeks", job.id, week)
            job.blocker = Blocker(week, weeks, w.k.chance(r["dataAccessShare"], "dataAccess", job.id, week))
        if job.phase in ("discovery", "build") and job.creeps < r["scopeCreepMaxPerEngagement"] \
                and w.k.chance(r["scopeCreepPerWeek"], "creep", job.id, week):
            job.creeps += 1
            share = r["scopeCreepMin"] + w.k.u("creepShare", job.id, week) * (r["scopeCreepMax"] - r["scopeCreepMin"])
            extra = job.scoped["build"] * share
            job.true_hours["build"] += extra
            job.pending_creep.append((week, "build", extra))


def milestones(w: World, week: int, log: WeekLog) -> None:
    for job in active_jobs(w, week):
        for phase in PHASES:
            due = job.due[phase] + job.extension.get(phase, 0)
            if due == week and phase not in job.done_week:
                log.slips.append((job.id, phase))
        blocked_long = job.blocker is not None and week - job.blocker.started >= 1
        if blocked_long or any(s[0] == job.id for s in log.slips):
            job.unhappy_weeks += 1
        else:
            job.unhappy_weeks = max(0, job.unhappy_weeks - 1)


def escalate(w: World, week: int, job: Job) -> list[str]:
    """What the delivery lead does with an escalation: unblock, agree a change request, reset expectations."""
    r = w.cfg["risks"]
    done: list[str] = []
    if job.blocker is not None:
        left = job.blocker.started + job.blocker.weeks - week
        job.blocker.weeks -= max(0, left - left // 2)
        done.append("unblocked sooner")
    kept = []
    for at, phase, extra in job.pending_creep:
        if week - at <= r["changeRequestWindowWeeks"]:
            weeks = math.ceil(extra / w.cfg["engagements"]["plannedWeeklyHours"][phase])
            started = PHASES.index(phase)
            for later in PHASES[started:]:
                job.extension[later] = job.extension.get(later, 0) + weeks
            if job.contract == "fixed":
                rate = w.catalog["profiles"][PROFILE_OF_PHASE[phase]]["billRatePerHour"]
                job.change_orders_eur += extra * rate
            done.append("change request agreed")
        else:
            kept.append((at, phase, extra))
    job.pending_creep = [c for c in kept if week - c[0] <= r["changeRequestWindowWeeks"]]
    job.unhappy_weeks = 0
    return done


def expire_creep(w: World, week: int) -> None:
    r = w.cfg["risks"]
    for job in active_jobs(w, week):
        job.pending_creep = [c for c in job.pending_creep if week - c[0] <= r["changeRequestWindowWeeks"]]


def apply_templates(w: World, job: Job, templates: set[str], saving_share: float) -> float:
    """At build start, work the team has a template for takes less time. Returns the true hours saved."""
    saved = 0.0
    for item in job.work_items:
        if item in templates:
            hours = w.catalog["workTypes"][item]["hours"] * saving_share
            saved += hours * (job.true_hours["build"] / max(1, job.scoped["build"]))
    job.true_hours["build"] = max(8.0, job.true_hours["build"] - saved)
    return saved


def rebaseline(job: Job, phase: str, week: int) -> None:
    """A phase that finished late moves the dates after it by the same amount, as a re-plan with the customer would."""
    late = week - (job.due[phase] + job.extension.get(phase, 0))
    if late <= 0:
        return
    for later in PHASES[PHASES.index(phase) + 1:]:
        job.extension[later] = job.extension.get(later, 0) + late
