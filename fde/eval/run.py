"""Runs each design week by week on the same simulated year and scores it.

This is the only module that sees both the world and the product. The product gets what a delivery manager gets:
engagements as scoped, hours logged, status notes, and pipelines to review; it never sees the truth.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fde.config import ROOT, load
from fde.product import escalation as esc
from fde.product import gate as product_gate
from fde.product import intake
from fde.product.model import Assignment, Engagement, EngagementState, Fde, PhaseScope, Plan
from fde.product.patterns import PatternLibrary
from fde.product.staffing import StaffingSettings, hot_streaks, plan_week
from fde.world import actors, notes, pipelines, sim
from fde.world.world import PHASES, PROFILE_OF_PHASE, Job, World


@dataclass
class Tally:
    milestones: list[dict[str, Any]] = field(default_factory=list)
    escalations: list[tuple[str, int, str]] = field(default_factory=list)
    customer_escalations: int = 0
    capacity_hours: float = 0.0
    billable_hours: float = 0.0
    template_hours: float = 0.0
    idle_hours: float = 0.0
    burnout_weeks: int = 0
    sick_weeks: int = 0
    revenue: float = 0.0
    cost: float = 0.0
    penalties: float = 0.0
    shipped: int = 0
    incidents: int = 0
    blocked_right: int = 0
    blocked_wrong: int = 0
    gate_runs: int = 0
    hours_saved: float = 0.0
    templates_built: list[str] = field(default_factory=list)
    week_load: list[dict[str, float]] = field(default_factory=list)
    declined: list[str] = field(default_factory=list)
    declined_fee: float = 0.0
    snapshot: dict[str, Any] | None = None


def roster_of(w: World) -> list[Fde]:
    return [Fde(p.id, p.name, p.profile, p.skills, p.capacity) for p in w.people]


def engagement_of(job: Job) -> Engagement:
    return Engagement(job.id, job.customer, job.sector, job.topology, job.contract, job.fixed_fee, job.start_week,
                      {p: PhaseScope(job.scoped[p], job.due[p]) for p in PHASES}, job.required, job.work_items)


# ---- baseline staffing ---------------------------------------------------------------------------------------------

def plan_by_hand(week: int, roster: list[Fde], available: dict[str, int], states: list[EngagementState],
                 last: Plan | None, overtime: float) -> Plan:
    """A busy manager: one person per engagement phase, full time, the same person as last week when possible; when a
    date is close, people work overtime. Skills are checked; load is not."""
    load: dict[str, int] = defaultdict(int)
    previous = {a.engagement_id: a.fde_id for a in (last.assignments if last else [])}
    out: list[Assignment] = []
    ordered = sorted((s for s in states if not s.done and s.engagement.start_week <= week),
                     key=lambda s: (s.due(s.phase), s.engagement.id))
    for st in ordered:
        profile = PROFILE_OF_PHASE[st.phase]
        cands = [f for f in roster if f.profile == profile and st.engagement.required_skills <= f.skills
                 and available.get(f.id, 0) > 0]
        keep = previous.get(st.engagement.id)
        cands.sort(key=lambda f: (f.id != keep, load[f.id], f.id))
        for f in cands:
            cap = available[f.id]
            urgent = st.due(st.phase) - week <= 1
            limit = int(cap * overtime) if urgent else cap
            hours = min(limit - load[f.id], cap)
            if hours >= 8:
                load[f.id] += hours
                out.append(Assignment(f.id, st.engagement.id, st.phase, hours))
                break
    return Plan(week, out, [])


def plan_first_free(week: int, roster: list[Fde], available: dict[str, int], states: list[EngagementState]) -> Plan:
    """Each phase gets what it needs from the first free people of its profile, by roster order."""
    load: dict[str, int] = defaultdict(int)
    out: list[Assignment] = []
    for st in sorted(states, key=lambda s: s.engagement.id):
        if st.done or st.engagement.start_week > week:
            continue
        need = math.ceil(st.remaining_estimate(st.phase) / max(1, st.due(st.phase) - week) / 8) * 8
        for f in roster:
            if need <= 0:
                break
            if f.profile != PROFILE_OF_PHASE[st.phase]:
                continue
            free = available.get(f.id, 0) - load[f.id]
            hours = min(need, free)
            if hours >= 8:
                load[f.id] += hours
                need -= hours
                out.append(Assignment(f.id, st.engagement.id, st.phase, hours))
    return Plan(week, out, [])


# ---- one design on one world ---------------------------------------------------------------------------------------

def run_design(root: Path, world_file: str, name: str, design: dict[str, Any], catalog: dict[str, Any],
               product: dict[str, Any], designs: dict[str, Any], snapshot_at: int | None = None,
               world_cfg: dict[str, Any] | None = None) -> tuple[Tally, World]:
    w = World(world_cfg, catalog) if world_cfg is not None else World.load(root, world_file, catalog)
    note_texts: dict[str, list[tuple[int, str]]] = defaultdict(list)
    gate_results: dict[str, dict[str, Any]] = {}
    roster = roster_of(w)
    settings = StaffingSettings.from_config(product)
    esc_settings = esc.EscalationSettings.from_config(product)
    library = PatternLibrary.from_config(product, catalog)
    jobs = {j.id: j for j in w.jobs}
    states: dict[str, EngagementState] = {}
    history: dict[str, list[esc.Signals]] = defaultdict(list)
    builders: dict[str, set[str]] = defaultdict(set)
    template_progress: dict[str, float] = defaultdict(float)
    hot: dict[str, int] = {}
    last: Plan | None = None
    t = Tally()
    true_saving = catalog["templateSavingShare"]

    for week in range(w.weeks):
        for job in w.jobs:
            if job.start_week == week:
                if design["intake"] == "engine":
                    verdict = intake.decide(week, engagement_of(job), list(states.values()), roster, catalog, product)
                    if not verdict.accept:
                        job.accepted = False
                        t.declined.append(job.id)
                        t.declined_fee += job.fixed_fee
                        continue
                states[job.id] = EngagementState(engagement_of(job), "discovery")
        avail = sim.available(w, week)
        live = [s for s in states.values() if not s.done]
        if design["staffing"] == "engine":
            plan = plan_week(week, roster, avail, live, last, hot, list(library.queued) if design["patterns"] else [],
                             settings, catalog)
        elif design["staffing"] == "by_hand":
            plan = plan_by_hand(week, roster, avail, live, last, designs["byHandOvertimeLoad"])
        else:
            plan = plan_first_free(week, roster, avail, live)
        hot = hot_streaks(plan, avail, hot, settings.hot_load)
        last = plan
        log = sim.work(w, week, [(a.fde_id, a.engagement_id, a.phase, a.hours) for a in plan.assignments])

        # Accounting for the week, after the ramp-up.
        counted = week >= w.cfg["warmupWeeks"]
        for p in (w.people if counted else []):
            worked = log.hours_by_person.get(p.id, 0.0)
            t.capacity_hours += p.capacity
            t.cost += p.capacity * catalog["profiles"][p.profile]["costPerHour"]
            t.idle_hours += max(0.0, avail[p.id] - worked)
            if avail[p.id] == 0:
                t.sick_weeks += 1
            if worked > p.capacity * w.cfg["people"]["hotLoad"] + 1e-9:
                t.burnout_weeks += 1
        if counted:
            t.week_load.append({pid: round(h / w.person(pid).capacity, 3) for pid, h in log.hours_by_person.items()})
        for a in plan.assignments:
            if a.engagement_id in jobs and jobs[a.engagement_id].phase == "build" and a.phase == "build":
                builders[a.engagement_id].add(a.fde_id)
        for item, hours in log.template_hours.items():
            t.template_hours += hours
            template_progress[item] += hours
            if template_progress[item] >= catalog["templateBuildHours"] and item not in library.templates:
                library.built(item)
                t.templates_built.append(item)
        for (jid, phase), hours in log.logged.items():
            job = jobs[jid]
            st = states[jid]
            before = st.logged.get(phase, 0.0)
            st.logged[phase] = before + hours
            if not counted:
                continue
            if job.contract == "tm":
                cap = job.scoped[phase] * designs["tmOverrunBillableShare"]
                billable = max(0.0, min(st.logged[phase], cap) - min(before, cap))
                t.revenue += billable * catalog["profiles"][PROFILE_OF_PHASE[phase]]["billRatePerHour"]
            else:
                # Fixed fee, recognised by percentage of completion (cost-to-cost), capped at the phase's share.
                scoped = job.scoped[phase]
                done = (min(st.logged[phase], scoped) - min(before, scoped)) / scoped
                t.revenue += job.fixed_fee / len(PHASES) * done
            t.billable_hours += hours
        for jid, phase in log.phase_done:
            job, st = jobs[jid], states[jid]
            sim.rebaseline(job, phase, week)
            if job.finished:
                st.done = True
            else:
                st.phase = job.phase
            if phase == "discovery":
                if design["patterns"]:
                    t.hours_saved += sim.apply_templates(w, job, library.templates, true_saving)
                    library.record(job.id, job.work_items)

        # Go-live gate.
        for jid in log.gate_due:
            job = jobs[jid]
            dep = pipelines.build(w, job, sorted(builders[jid]))
            fails = pipelines.fails_in_production(w, job, dep)
            ship = True
            if design["gate"]:
                t.gate_runs += 1
                result = product_gate.review(
                    product_gate.PipelineConfig.from_json(dep.config), job.topology,
                    [product_gate.SourceDoc(d.id, d.content, d.department) for d in dep.documents],
                    [product_gate.GoldenQuestion(q.question, q.fact, q.source_id) for q in dep.golden],
                    product, catalog)
                gate_results[jid] = result.to_json()
                if not result.passed:
                    ship = False
                    if fails:
                        t.blocked_right += 1
                    else:
                        t.blocked_wrong += 1
                    p = w.cfg["pipelines"]
                    job.true_hours["go_live"] += w.k.between(p["reworkHoursMin"], p["reworkHoursMax"], "rework", jid)
            if ship:
                t.shipped += 1
                if fails:
                    t.incidents += 1
                    job.incident = True
                    job.true_hours["go_live"] += w.cfg["pipelines"]["incidentHours"]
                    t.penalties += w.cfg["pipelines"]["incidentPenaltyEur"]
                    if w.k.chance(w.cfg["risks"]["customerEscalationOnIncident"], "custEscInc", jid):
                        t.customer_escalations += 1
            job.gate_due = False

        sim.events(w, week)

        # Status notes and escalation.
        for job in sim.active_jobs(w, week):
            st = states[job.id]
            truth = notes.truth(w, job, week)
            read = actors.read_note(w, truth, job.id, week)
            if snapshot_at is not None:
                note_texts[job.id].append((week, notes.render(w, job, week, truth)))
            signals = esc.Signals(read.blocker, read.data_access, read.scope_change, read.sentiment, read.pct_done)
            history[job.id].append(signals)
            if read.pct_done is not None:
                st.reported_done[st.phase] = read.pct_done
            if design["escalation"] != "engine":
                continue
            planned = sum(a.hours for a in plan.assignments if a.engagement_id == job.id and a.phase == st.phase)
            planned_to_due = planned * max(1, st.due(st.phase) - week)
            if st.escalated_week is not None and week - st.escalated_week < 2:
                continue
            decision = esc.decide(st, history[job.id], planned_to_due, week, esc_settings)
            if decision.escalate:
                sim.escalate(w, week, job)
                st.escalated_week = week
                t.escalations.append((job.id, week, decision.kind))
        sim.expire_creep(w, week)

        # Milestones.
        sim.milestones(w, week, log)
        for jid, phase in log.slips:
            job, st = jobs[jid], states[jid]
            due = job.due[phase] + job.extension.get(phase, 0)
            flagged = st.escalated_week is not None and st.escalated_week <= due - 1 \
                and st.escalated_week >= job.due[phase] - 6
            if not flagged and w.k.chance(w.cfg["risks"]["customerEscalationOnSurpriseSlip"], "custEsc", jid, phase):
                t.customer_escalations += 1
            if design["escalation"] == "on_slip":
                sim.escalate(w, week, job)
                st.escalated_week = week
                t.escalations.append((jid, week, "slip"))
            if due >= w.cfg["warmupWeeks"]:
                t.milestones.append({"job": jid, "phase": phase, "due": due, "slipped": True, "flagged": flagged})
        for job in w.jobs:
            st = states.get(job.id)
            if st is not None and job.accepted:
                st.due_extension = dict(job.extension)
        if snapshot_at is not None and week == snapshot_at:
            t.snapshot = {"week": week, "states": states, "notes": note_texts, "plan": plan, "hot": hot,
                          "library": library, "gates": gate_results, "escalations": list(t.escalations),
                          "declined": list(t.declined)}
            return t, w

    # Milestones met: every phase due inside the year that was not recorded as slipped.
    slipped = {(m["job"], m["phase"]) for m in t.milestones}
    for job in w.jobs:
        if not job.accepted:
            continue
        for phase in PHASES:
            due = job.due[phase] + job.extension.get(phase, 0)
            if w.cfg["warmupWeeks"] <= due < w.weeks and (job.id, phase) not in slipped:
                t.milestones.append({"job": job.id, "phase": phase, "due": due, "slipped": False, "flagged": False})
    t.revenue += sum(j.change_orders_eur for j in w.jobs)
    t.cost += t.penalties
    return t, w


def score(t: Tally, w: World) -> dict[str, Any]:
    ms = t.milestones
    met = sum(1 for m in ms if not m["slipped"])
    slips = [m for m in ms if m["slipped"]]
    surprise = sum(1 for m in slips if not m["flagged"])
    margin = t.revenue - t.cost
    return {
        "milestones": len(ms),
        "milestonesOnPlan": round(met / max(1, len(ms)), 4),
        "slips": len(slips),
        "surpriseSlips": surprise,
        "customerEscalations": t.customer_escalations,
        "escalationsRaised": len(t.escalations),
        "utilization": round(t.billable_hours / max(1.0, t.capacity_hours), 4),
        "idleHours": round(t.idle_hours),
        "burnoutWeeks": t.burnout_weeks,
        "sickWeeks": t.sick_weeks,
        "revenueEur": round(t.revenue),
        "costEur": round(t.cost),
        "marginEur": round(margin),
        "marginShare": round(margin / max(1.0, t.revenue), 4),
        "pipelinesShipped": t.shipped,
        "productionIncidents": t.incidents,
        "gateRuns": t.gate_runs,
        "blockedThatWouldHaveFailed": t.blocked_right,
        "blockedThatWouldHavePassed": t.blocked_wrong,
        "templatesBuilt": len(t.templates_built),
        "templateHours": round(t.template_hours),
        "hoursSavedByTemplates": round(t.hours_saved),
        "engagementsDeclined": len(t.declined),
        "declinedFeeEur": round(t.declined_fee),
    }


def per_engagement_on_plan(t: Tally) -> dict[str, float]:
    by: dict[str, list[bool]] = defaultdict(list)
    for m in t.milestones:
        by[m["job"]].append(not m["slipped"])
    return {j: sum(v) / len(v) for j, v in by.items()}


def paired_bootstrap(a: dict[str, float], b: dict[str, float], seed: str, n: int = 2000) -> dict[str, float]:
    keys = sorted(set(a) & set(b))
    diffs = [a[k] - b[k] for k in keys]
    rng = random.Random(seed)
    means = sorted(sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs) for _ in range(n))
    return {"difference": round(sum(diffs) / len(diffs), 4), "lo90": round(means[int(n * 0.05)], 4),
            "hi90": round(means[int(n * 0.95) - 1], 4), "engagements": len(keys)}


def evaluate(root: Path, world_file: str, name: str) -> dict[str, Any]:
    catalog, product, designs = load("catalog.json", root), load("product.json", root), load("designs.json", root)
    out: dict[str, Any] = {"designs": {}}
    tallies: dict[str, Tally] = {}
    world: World | None = None
    for key, design in designs["designs"].items():
        t, w = run_design(root, world_file, key, design, catalog, product, designs)
        tallies[key] = t
        world = w
        s = score(t, w)
        s["label"] = design["label"]
        out["designs"][key] = s
    assert world is not None
    out["world"] = {
        "name": name, "seed": world.cfg["seed"], "weeks": world.weeks, "people": len(world.people),
        "engagements": len(world.jobs),
        "sectors": {s: sum(1 for j in world.jobs if j.sector == s) for s in ("public", "manufacturing", "insurance",
                                                                            "finance")},
        "airGapped": sum(1 for j in world.jobs if j.topology == "air_gapped"),
    }
    engine = per_engagement_on_plan(tallies["engine"])
    out["milestoneDifference"] = {k: paired_bootstrap(engine, per_engagement_on_plan(tallies[k]), f"{name}-{k}")
                                  for k in ("by_hand", "first_free")}
    out["teamLoad"] = _team_load(tallies["engine"], tallies["by_hand"], world)
    return out


def _team_load(engine: Tally, by_hand: Tally, w: World) -> dict[str, Any]:
    def weekly(t: Tally) -> list[float]:
        return [round(sum(wk.values()) / max(1, len(w.people)), 3) for wk in t.week_load]
    return {"engine": weekly(engine), "by_hand": weekly(by_hand)}


def main_root() -> Path:
    return ROOT
