"""The manager's API: team load and the week's plan, engagement health with the escalation agent, go-live reviews,
intake decisions and the patterns that should become product.

Run: uvicorn fde.service.app:app --port 8790. Keys and settings come from config/product.json; state starts from
demo/seed.json; DATABASE_URL moves the audit trail to Postgres.
"""

from __future__ import annotations

import json
import os
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import fde  # noqa: F401  (switches Haystack telemetry off)
from fde.config import ROOT, load
from fde.product import escalation as esc
from fde.product import gate as product_gate
from fde.product import intake as product_intake
from fde.product.model import Engagement, EngagementState, Fde, PhaseScope, Plan, Assignment, PHASES
from fde.product.patterns import PatternLibrary
from fde.product.staffing import StaffingSettings, hot_streaks, plan_week
from fde.service.store import Audit, MemoryLog, PostgresLog


class NoteIn(BaseModel):
    text: str = Field(min_length=3, max_length=8000)


class ReviewIn(BaseModel):
    config: dict[str, Any] | None = None


class PhaseIn(BaseModel):
    scopedHours: int = Field(gt=0, le=5000)
    dueWeek: int = Field(ge=0, le=520)


class IntakeIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    customer: str = Field(min_length=1, max_length=120)
    sector: str = "public"
    topology: str = "self_hosted"
    contract: str = "tm"
    phases: dict[str, PhaseIn]
    requiredSkills: list[str] = []


class Engine:
    """The service's state: the team, live engagements, the week's plan and every note, decision and review."""

    def __init__(self, seed: dict[str, Any], audit: Audit, reader: esc.SignalReader) -> None:
        self.catalog = load("catalog.json")
        self.product = load("product.json")
        self.settings = StaffingSettings.from_config(self.product)
        self.esc_settings = esc.EscalationSettings.from_config(self.product)
        self.audit = audit
        self.reader = reader
        self.lock = threading.Lock()
        self.week: int = seed["week"]
        self.roster = [Fde(r["id"], r["name"], r["profile"], frozenset(r["skills"]), r["capacityHours"])
                       for r in seed["roster"]]
        self.states: dict[str, EngagementState] = {}
        self.notes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.history: dict[str, list[esc.Signals]] = defaultdict(list)
        self.gates: dict[str, dict[str, Any]] = {}
        for e in seed["engagements"]:
            eng = Engagement(e["id"], e["customer"], e["sector"], e["topology"], e["contract"], e["fixedFee"],
                             e["startWeek"], {p: PhaseScope(v["scopedHours"], v["dueWeek"]) for p, v in
                                              e["phases"].items()}, frozenset(e["requiredSkills"]),
                             tuple(e["workItems"]))
            st = EngagementState(eng, e["phase"], {k: float(v) for k, v in e["logged"].items()},
                                 dict(e["reportedDone"]), {k: int(v) for k, v in e["dueExtension"].items()},
                                 e["escalatedWeek"], e["done"])
            self.states[eng.id] = st
            if e.get("gate"):
                self.gates[eng.id] = e["gate"]
            for n in e["notes"]:
                signals = self.reader.read(n["text"])
                self.history[eng.id].append(signals)
                self.notes[eng.id].append({"week": n["week"], "text": n["text"], "signals": signals.to_json(),
                                           "decision": None})
        self.plan = Plan(self.week, [Assignment(a["fdeId"], a["engagementId"], a["phase"], a["hours"])
                                     for a in seed["plan"]], [])
        self.hot: dict[str, int] = dict(seed["hotStreaks"])
        self.library = PatternLibrary.from_config(self.product, self.catalog)
        for item, engagements in seed["patterns"]["seen"].items():
            self.library.seen[item] = set(engagements)
        self.library.templates = set(seed["patterns"]["templates"])
        self.reviews = {r["engagementId"]: r for r in seed["reviews"]}
        self.declined: list[str] = list(seed["declined"])
        self.counters: Counter[str] = Counter()

    def available(self) -> dict[str, int]:
        return {f.id: f.capacity_hours for f in self.roster}

    def live(self) -> list[EngagementState]:
        return [s for s in self.states.values() if not s.done]

    def planned(self, eid: str, phase: str) -> int:
        return sum(a.hours for a in self.plan.assignments if a.engagement_id == eid and a.phase == phase)

    def latest_decision(self, eid: str) -> dict[str, Any] | None:
        for n in reversed(self.notes.get(eid, [])):
            if n["decision"] is not None:
                return n["decision"]
        return None


def _reader(product: dict[str, Any]) -> esc.SignalReader:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        m = product["model"]
        return esc.AnthropicReader(m["apiUrl"], key, m["name"], m["maxTokens"])
    return esc.KeywordReader()


def create_app(seed_path: Path | None = None, database_url: str | None = None) -> FastAPI:
    product = load("product.json")
    seed = json.loads((seed_path or ROOT / "demo" / "seed.json").read_text(encoding="utf-8"))
    url = database_url if database_url is not None else os.environ.get("DATABASE_URL", "")
    audit = Audit(PostgresLog(url) if url else MemoryLog())
    engine = Engine(seed, audit, _reader(product))
    keys = {k["key"]: k for k in product["apiKeys"]}
    app = FastAPI(title="fde-delivery-engine", version="1.0.0")
    app.state.engine = engine

    @app.middleware("http")
    async def count(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        engine.counters[f'http_requests_total{{status="{response.status_code}"}}'] += 1
        return response

    def caller(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        k = keys.get(x_api_key or "")
        if k is None:
            raise HTTPException(401, "a valid X-Api-Key header is needed")
        return k

    def manager(c: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        if c["role"] != "manager":
            raise HTTPException(403, "only the delivery manager can do this")
        return c

    def state_of(eid: str) -> EngagementState:
        st = engine.states.get(eid)
        if st is None:
            raise HTTPException(404, f"no engagement {eid}")
        return st

    def summary(st: EngagementState) -> dict[str, Any]:
        e = st.engagement
        decision = engine.latest_decision(e.id)
        return {"id": e.id, "customer": e.customer, "sector": e.sector, "topology": e.topology,
                "contract": e.contract, "phase": st.phase, "done": st.done, "dueWeek": st.due(st.phase),
                "weeksLeft": st.due(st.phase) - engine.week, "remainingHours": round(st.remaining_estimate(st.phase)),
                "plannedHours": engine.planned(e.id, st.phase), "escalatedWeek": st.escalated_week,
                "risk": decision["score"] if decision else 0.0,
                "riskReasons": decision["reasons"] if decision else [],
                "gate": engine.gates.get(e.id, {}).get("passed")}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        lines = [f"fde_{k} {v}" for k, v in sorted(engine.counters.items())]
        load_ = sum(engine.plan.hours_of(f.id) for f in engine.roster) / max(1, sum(engine.available().values()))
        lines.append(f"fde_planned_utilization {load_:.4f}")
        lines.append(f"fde_live_engagements {len(engine.live())}")
        return "\n".join(lines) + "\n"

    @app.get("/api/overview")
    def overview(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        live = engine.live()
        avail = engine.available()
        planned = sum(engine.plan.hours_of(f.id) for f in engine.roster)
        at_risk = [summary(s) for s in live if (engine.latest_decision(s.engagement.id) or {}).get("escalate")]
        return {"week": engine.week, "liveEngagements": len(live), "people": len(engine.roster),
                "plannedUtilization": round(planned / max(1, sum(avail.values())), 4),
                "hotPeople": sorted(k for k, v in engine.hot.items() if v > 0),
                "atRisk": at_risk, "declined": engine.declined,
                "phases": {p: sum(1 for s in live if s.phase == p) for p in PHASES}}

    @app.get("/api/team")
    def team(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        out = []
        for f in engine.roster:
            work = [{"engagementId": a.engagement_id, "phase": a.phase, "hours": a.hours}
                    for a in engine.plan.assignments if a.fde_id == f.id]
            hours = engine.plan.hours_of(f.id)
            out.append({"id": f.id, "name": f.name, "profile": f.profile, "skills": sorted(f.skills),
                        "capacityHours": f.capacity_hours, "plannedHours": hours,
                        "load": round(hours / f.capacity_hours, 3), "hotStreak": engine.hot.get(f.id, 0),
                        "work": work})
        return {"week": engine.week, "target": engine.settings.utilization_target,
                "hotLoad": engine.settings.hot_load, "people": out, "warnings": engine.plan.warnings}

    @app.post("/api/plan")
    def replan(c: dict[str, Any] = Depends(manager)) -> dict[str, Any]:
        with engine.lock:
            avail = engine.available()
            plan = plan_week(engine.week, engine.roster, avail, engine.live(), engine.plan, engine.hot,
                             list(engine.library.queued), engine.settings, engine.catalog)
            engine.hot = hot_streaks(plan, avail, engine.hot, engine.settings.hot_load)
            engine.plan = plan
            engine.audit.record(engine.week, c["actor"], "plan.made", f"week {engine.week}",
                                {"assignments": len(plan.assignments), "warnings": plan.warnings})
        return team(c)

    @app.get("/api/engagements")
    def engagements(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        rows = [summary(s) for s in engine.states.values()]
        rows.sort(key=lambda r: (r["done"], -r["risk"], r["weeksLeft"], r["id"]))
        return {"week": engine.week, "engagements": rows}

    @app.get("/api/engagements/{eid}")
    def engagement(eid: str, _: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        st = state_of(eid)
        e = st.engagement
        phases = [{"phase": p, "scopedHours": e.phases[p].scoped_hours, "dueWeek": st.due(p),
                   "loggedHours": round(st.logged.get(p, 0.0)), "reportedDone": st.reported_done.get(p)}
                  for p in PHASES]
        team_ = [{"fdeId": a.fde_id, "hours": a.hours, "phase": a.phase}
                 for a in engine.plan.assignments if a.engagement_id == eid]
        return {**summary(st), "phases": phases, "notes": engine.notes.get(eid, []), "team": team_,
                "requiredSkills": sorted(e.required_skills), "workItems": list(e.work_items),
                "gateResult": engine.gates.get(eid), "awaitingReview": eid in engine.reviews}

    @app.post("/api/engagements/{eid}/notes")
    def add_note(eid: str, body: NoteIn, c: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        st = state_of(eid)
        with engine.lock:
            try:
                signals = engine.reader.read(body.text)
            except Exception as exc:  # the reader is a model call: a failure must not lose the note
                raise HTTPException(502, f"the note could not be read: {exc}") from exc
            engine.history[eid].append(signals)
            if signals.pct_done is not None:
                st.reported_done[st.phase] = signals.pct_done
            planned = engine.planned(eid, st.phase) * max(1, st.due(st.phase) - engine.week)
            decision = esc.decide(st, engine.history[eid], planned, engine.week, engine.esc_settings)
            d = {"escalate": decision.escalate, "score": decision.score, "reasons": decision.reasons,
                 "kind": decision.kind}
            engine.notes[eid].append({"week": engine.week, "text": body.text, "signals": signals.to_json(),
                                      "decision": d, "by": c["actor"]})
            engine.counters["notes_read_total"] += 1
            if decision.escalate and (st.escalated_week is None or engine.week - st.escalated_week >= 2):
                st.escalated_week = engine.week
                engine.counters[f'escalations_total{{kind="{decision.kind}"}}'] += 1
            engine.audit.record(engine.week, c["actor"], "note.read", eid, {"signals": signals.to_json(),
                                                                            "decision": d})
        return {"signals": signals.to_json(), "decision": d}

    @app.get("/api/reviews")
    def reviews(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        return {"reviews": [{"engagementId": r["engagementId"], "topology": r["topology"], "config": r["config"],
                             "documents": len(r["documents"]), "goldenQuestions": len(r["golden"]),
                             "result": engine.gates.get(r["engagementId"])} for r in engine.reviews.values()]}

    @app.post("/api/reviews/{eid}/run")
    def run_review(eid: str, body: ReviewIn, c: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        r = engine.reviews.get(eid)
        if r is None:
            raise HTTPException(404, f"no pipeline awaiting review for {eid}")
        config = {**r["config"], **(body.config or {})}
        try:
            cfg = product_gate.PipelineConfig.from_json(config)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, f"pipeline config is incomplete: {exc}") from exc
        if not 1 <= cfg.top_k <= 50 or not 5 <= cfg.split_length <= 2000 or not 0 <= cfg.split_overlap < cfg.split_length:
            raise HTTPException(422, "top_k, split_length or split_overlap is out of range")
        result = product_gate.review(cfg, r["topology"],
                                     [product_gate.SourceDoc(d["id"], d["content"], d["department"])
                                      for d in r["documents"]],
                                     [product_gate.GoldenQuestion(q["question"], q["fact"], q["sourceId"])
                                      for q in r["golden"]], engine.product, engine.catalog).to_json()
        result["config"] = config
        with engine.lock:
            engine.gates[eid] = result
            engine.counters[f'gate_runs_total{{passed="{str(result["passed"]).lower()}"}}'] += 1
            engine.audit.record(engine.week, c["actor"], "gate.run", eid,
                                {"passed": result["passed"], "recall": result["recall"],
                                 "grounded": result["grounded"], "findings": result["findings"]})
        return result

    @app.post("/api/intake")
    def intake(body: IntakeIn, c: dict[str, Any] = Depends(manager)) -> dict[str, Any]:
        if set(body.phases) != set(PHASES):
            raise HTTPException(422, f"phases must be exactly {', '.join(PHASES)}")
        eng = Engagement(body.id, body.customer, body.sector, body.topology, body.contract, 0, engine.week,
                         {p: PhaseScope(v.scopedHours, v.dueWeek) for p, v in body.phases.items()},
                         frozenset(body.requiredSkills), ())
        d = product_intake.decide(engine.week, eng, engine.live(), engine.roster, engine.catalog, engine.product)
        engine.audit.record(engine.week, c["actor"], "intake.decided", body.id,
                            {"accept": d.accept, "reason": d.reason})
        return {"accept": d.accept, "reason": d.reason, "loadByProfile": d.load_by_profile}

    @app.get("/api/patterns")
    def patterns(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        labels = {k: v["label"] for k, v in engine.catalog["workTypes"].items()}
        rows = [{**r, "label": labels.get(r["workType"], r["workType"])} for r in engine.library.product_requests()]
        return {"patterns": rows, "templateAfter": engine.library.template_after}

    @app.get("/api/results")
    def results(_: dict[str, Any] = Depends(caller)) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in ("dev", "heldout"):
            p = ROOT / "reports" / f"{name}.json"
            out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        return out

    @app.get("/api/audit/verify")
    def verify(_: dict[str, Any] = Depends(manager)) -> dict[str, Any]:
        return engine.audit.verify()

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="console")
    return app


app = create_app() if os.environ.get("FDE_NO_APP") != "1" else None
