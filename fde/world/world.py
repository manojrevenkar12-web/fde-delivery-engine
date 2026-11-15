"""The simulated services business: who is on the team, which engagements arrive, and what really happens on them.

The world keeps the truth: true effort behind every scope, each person's productivity and fatigue, blockers and scope
creep as they happen, and hidden defects in the pipelines teams build. Designs see only what a delivery manager
would: scopes, logged hours, status notes and gate results.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fde.keyed import Keyed
from fde.world import corpus

PHASES = ("discovery", "build", "go_live", "hypercare")
PROFILE_OF_PHASE = {"discovery": "advisory", "build": "builder", "go_live": "operating", "hypercare": "support"}
_CUSTOMERS = ["Landkreis Elbtal", "Stadtwerke Havelberg", "Bezirksamt Spreeufer", "Ministerium Nordmark",
              "Rheinwerk Maschinenbau", "Kessler Antriebe", "Nordlicht Versicherung", "Alpina Leben", "Merkur Bank",
              "Hanse Kredit", "Landesamt Seenplatte", "Gemeinde Eichwalde", "Vogt Präzision", "Pfalz Assekuranz",
              "Börde Finanz", "Stadt Kranichfeld", "Agentur Weststrand", "Hartmann Hydraulik"]


@dataclass
class Person:
    id: str
    name: str
    profile: str
    skills: frozenset[str]
    capacity: int
    productivity: float
    fatigue: int = 0
    sick_until: int = -1


@dataclass
class Blocker:
    started: int
    weeks: int
    data_access: bool


@dataclass
class Job:
    """One engagement with its truth."""

    id: str
    customer: str
    sector: str
    topology: str
    contract: str
    fixed_fee: int
    start_week: int
    german: bool
    required: frozenset[str]
    work_items: tuple[str, ...]
    scoped: dict[str, int]
    due: dict[str, int]
    true_hours: dict[str, float]
    progress: dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in PHASES})
    phase: str = "discovery"
    done_week: dict[str, int] = field(default_factory=dict)
    extension: dict[str, int] = field(default_factory=dict)
    blocker: Blocker | None = None
    pending_creep: list[tuple[int, str, float]] = field(default_factory=list)
    creeps: int = 0
    change_orders_eur: float = 0.0
    unhappy_weeks: int = 0
    team_on: set[str] = field(default_factory=set)
    gate_due: bool = False
    pipeline: dict[str, Any] | None = None
    defects: list[str] = field(default_factory=list)
    incident: bool = False
    customer_escalations: int = 0
    finished: bool = False
    accepted: bool = True

    def remaining(self, phase: str) -> float:
        return max(0.0, self.true_hours[phase] - self.progress[phase])


class World:
    def __init__(self, cfg: dict[str, Any], catalog: dict[str, Any]) -> None:
        self.cfg = cfg
        self.catalog = catalog
        self.k = Keyed(cfg["seed"])
        self.weeks: int = cfg["weeks"]
        self.people: list[Person] = []
        self.jobs: list[Job] = []
        self.corpora: dict[str, list[corpus.Programme]] = {}
        self._team()
        self._engagements()

    @staticmethod
    def load(root: Path, name: str, catalog: dict[str, Any]) -> "World":
        return World(json.loads((root / "config" / name).read_text(encoding="utf-8")), catalog)

    # ---- generation ----------------------------------------------------------------------------------------------

    def _team(self) -> None:
        t = self.cfg["team"]
        first = ["Lena", "Jonas", "Amira", "Felix", "Sofia", "Malik", "Hanna", "Tobias", "Mira", "Noah", "Elif",
                 "Paul", "Ida", "Ben", "Clara", "Yusuf", "Greta", "Aaron"]
        n = 0
        for profile in ("advisory", "builder", "operating", "support"):
            for i in range(t[profile]):
                pid = f"f-{profile}-{i + 1:02d}"
                skills = frozenset(s for s, share in t["skillShare"].items() if self.k.chance(share, "skill", pid, s))
                capacity = 32 if self.k.chance(t["partTimeShare"], "parttime", pid) else 40
                prod = t["productivityMin"] + self.k.u("prod", pid) * (t["productivityMax"] - t["productivityMin"])
                self.people.append(Person(pid, first[n % len(first)], profile, skills, capacity, prod))
                n += 1

    def _engagements(self) -> None:
        e = self.cfg["engagements"]
        arrivals = 0
        for week in range(self.weeks):
            count = self._poisson(e["arrivalsPerWeek"], "arrivals", week)
            for j in range(count):
                self.jobs.append(self._job(f"E{arrivals + 1:03d}", week))
                arrivals += 1

    def _poisson(self, mean: float, purpose: str, *ids: object) -> int:
        limit, p, n = math.exp(-mean), 1.0, 0
        while True:
            p *= self.k.u(purpose, *ids, n)
            if p < limit:
                return n
            n += 1

    def _weighted(self, weights: dict[str, float], purpose: str, *ids: object) -> str:
        u, acc = self.k.u(purpose, *ids), 0.0
        items = [(k, v) for k, v in weights.items() if not k.startswith("_")]
        total = sum(v for _, v in items)
        for key, w in items:
            acc += w / total
            if u < acc:
                return key
        return items[-1][0]

    def _job(self, jid: str, week: int) -> Job:
        e = self.cfg["engagements"]
        sector = self._weighted(e["sectors"], "sector", jid)
        topology = self._weighted(e["topologies"]["public" if sector == "public" else "other"], "topology", jid)
        german = sector == "public" or self.k.chance(e["germanOtherShare"], "german", jid)
        work_types = list(self.catalog["workTypes"].keys())
        n_items = self.k.between(e["workItemsMin"], e["workItemsMax"], "items", jid)
        items: list[str] = []
        for i in range(n_items * 3):
            if len(items) >= n_items:
                break
            w = work_types[self.k.pick(len(work_types), "item", jid, i)]
            if w not in items:
                items.append(w)
        if topology == "air_gapped" and "airgap_model_packaging" not in items:
            items.append("airgap_model_packaging")
        required = set()
        if german:
            required.add("german")
        if sector == "public" and topology == "air_gapped":
            required.add("clearance")
        scoped: dict[str, int] = {}
        for phase in PHASES:
            lo, hi = e["scope"][phase]
            scoped[phase] = int(round(self.k.between(lo, hi, "scope", jid, phase) / 8.0)) * 8
        scoped["build"] += sum(self.catalog["workTypes"][w]["hours"] for w in items)
        due: dict[str, int] = {}
        at = week
        for phase in PHASES:
            at += math.ceil(scoped[phase] / e["plannedWeeklyHours"][phase]) + e["bufferWeeks"]
            due[phase] = at
        true_hours = {p: scoped[p] * self.k.lognormal(e["overrunSigma"], "overrun", jid, p) for p in PHASES}
        contract = "fixed" if self.k.chance(e["fixedFeeShare"], "contract", jid) else "tm"
        rates = {p: self.catalog["profiles"][PROFILE_OF_PHASE[p]]["billRatePerHour"] for p in PHASES}
        fee = int(sum(scoped[p] * rates[p] for p in PHASES) * 1.05)
        customer = _CUSTOMERS[self.k.pick(len(_CUSTOMERS), "customer", jid)]
        return Job(jid, customer, sector, topology, contract, fee, week, german, frozenset(required), tuple(items),
                   scoped, due, true_hours)

    def corpus_for(self, job: Job) -> list[corpus.Programme]:
        if job.id not in self.corpora:
            n = self.cfg["pipelines"]["programsPerCorpus"]
            self.corpora[job.id] = corpus.programmes(self.k, job.id, job.german, n)
        return self.corpora[job.id]

    def person(self, pid: str) -> Person:
        return next(p for p in self.people if p.id == pid)
