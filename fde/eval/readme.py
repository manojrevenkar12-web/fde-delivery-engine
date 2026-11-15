"""Writes README.md from the reports. Every number in it comes from reports/*.json, config/*.json or the tests,
so CI can regenerate it and fail when it drifts."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from fde.eval import gate as gate_mod

ORDER = ["engine", "by_hand", "first_free", "engine_no_gate", "engine_no_escalation", "engine_no_patterns",
         "engine_accept_all"]
SHORT = {
    "engine": "**Engine**",
    "by_hand": "By hand (baseline)",
    "first_free": "First free person",
    "engine_no_gate": "Engine, no go-live gate",
    "engine_no_escalation": "Engine, no escalation agent",
    "engine_no_patterns": "Engine, no templates",
    "engine_accept_all": "Engine, accepts every opportunity",
}


def _pct(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}%"


def _eur(x: float) -> str:
    return f"€{x / 1000:,.0f}k"


def _count_tests(root: Path) -> tuple[int, int]:
    py = 0
    for f in (root / "tests").glob("test_*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        py += sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    web = 0
    for f in (root / "web" / "src").rglob("*.test.tsx"):
        web += f.read_text(encoding="utf-8").count("\n  it(")
    return py, web


def _table(report: dict[str, Any]) -> list[str]:
    out = ["| Design | Milestones on plan | Surprise slips | Customer escalations | Utilization | "
           "Person-weeks above 90% load | Production incidents | Margin | Declined |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k in ORDER:
        d = report["designs"].get(k)
        if d is None:
            continue
        out.append(f"| {SHORT[k]} | {_pct(d['milestonesOnPlan'], 1)} | {d['surpriseSlips']} | "
                   f"{d['customerEscalations']} | {_pct(d['utilization'], 1)} | {d['burnoutWeeks']} | "
                   f"{d['productionIncidents']} | {_pct(d['marginShare'], 1)} | {d['engagementsDeclined']} |")
    return out


def _gate_block(gate: dict[str, Any], report: dict[str, Any]) -> list[str]:
    verdict = gate_mod.check(gate, report)
    return ["```", *verdict["lines"], "```"]


def _world_line(w: dict[str, Any]) -> str:
    s = w["sectors"]
    return (f"{w['weeks']} weeks, {w['people']} forward-deployed engineers, {w['engagements']} opportunities "
            f"({s['public']} public sector, {s['finance']} finance, {s['insurance']} insurance, "
            f"{s['manufacturing']} manufacturing, {w['airGapped']} air-gapped), seed `{w['seed']}`")


def render(root: Path) -> str:
    dev = json.loads((root / "reports/dev.json").read_text(encoding="utf-8"))
    held_path = root / "reports/heldout.json"
    held = json.loads(held_path.read_text(encoding="utf-8")) if held_path.exists() else None
    gate = json.loads((root / "config/gate.json").read_text(encoding="utf-8"))
    product = json.loads((root / "config/product.json").read_text(encoding="utf-8"))
    py_tests, web_tests = _count_tests(root)

    e, b, ff = dev["designs"]["engine"], dev["designs"]["by_hand"], dev["designs"]["first_free"]
    ng, ne = dev["designs"]["engine_no_gate"], dev["designs"]["engine_no_escalation"]
    np_, na = dev["designs"]["engine_no_patterns"], dev["designs"]["engine_accept_all"]
    diff = dev["milestoneDifference"]["by_hand"]
    load_e, load_b = dev["teamLoad"]["engine"], dev["teamLoad"]["by_hand"]

    tiles = [
        ("Milestones on plan", f"{_pct(e['milestonesOnPlan'])}", f"by hand {_pct(b['milestonesOnPlan'])}"),
        ("Surprise slips", f"{e['surpriseSlips']}", f"by hand {b['surpriseSlips']}"),
        ("Person-weeks above 90% load", f"{e['burnoutWeeks']}", f"by hand {b['burnoutWeeks']}"),
        ("Production incidents", f"{e['productionIncidents']}", f"by hand {b['productionIncidents']}"),
        ("Margin", f"{_pct(e['marginShare'], 1)}", f"by hand {_pct(b['marginShare'], 1)}"),
        ("Customer escalations", f"{e['customerEscalations']}", f"by hand {b['customerEscalations']}"),
    ]

    lines: list[str] = []
    add = lines.append
    add("# fde-delivery-engine")
    add("")
    add("The delivery engine of a forward-deployed engineering team shipping Haystack into enterprise and "
        "public-sector production: staffing by FDE profile against utilization and burnout, a go-live gate that "
        "measures customer RAG pipelines, an escalation agent, and reusable patterns from the field.")
    add("")
    add("It is written from the seat of the manager who runs that team. Every Monday the manager has the same "
        "questions: who works on what this week, which engagement is about to slip and needs a call to the customer, "
        "is this pipeline good enough to go live, which piece of work have we built twice and should turn into "
        "a template, and can we take the next opportunity without burning the team. This repository answers each "
        "one in code, and measures the answers on a simulated year of engagements before trusting them.")
    add("")
    add("![The delivery desk: engagements, the escalation verdict on a status note](docs/console-engagements.png)")
    add("")
    add("## Dashboard")
    add("")
    add(f"Dev year: {_world_line(dev['world'])}. Every design below runs on the same opportunities, the same "
        "people and the same luck.")
    add("")
    add("| | Engine | Note |")
    add("|---|---:|---|")
    for name, value, note in tiles:
        add(f"| {name} | **{value}** | {note} |")
    add(f"| Per-engagement gain in milestones on plan | **+{100 * diff['difference']:.1f} pts** | paired bootstrap over "
        f"{diff['engagements']} engagements, 90% interval {100 * diff['lo90']:.1f} to {100 * diff['hi90']:.1f} |")
    add(f"| Average team load | **{_pct(sum(load_e) / len(load_e))}** | by hand {_pct(sum(load_b) / len(load_b))}, "
        f"target {_pct(product['staffing']['utilizationTarget'])} |")
    add(f"| Pipelines the gate held back | **{e['blockedThatWouldHaveFailed']}** | would have failed in production, "
        f"{e['blockedThatWouldHavePassed']} held back that would have passed |")
    add(f"| Templates built from repeated work | **{e['templatesBuilt']}** | {e['hoursSavedByTemplates']} hours saved "
        f"for {e['templateHours']} hours spent building them |")
    add(f"| Tests | **{py_tests + web_tests}** | {py_tests} Python, {web_tests} console |")
    add("")
    add("### Every design on the dev year")
    add("")
    lines.extend(_table(dev))
    add("")
    add("\"Person-weeks above 90% load\" counts weeks in which one person was planned above 90% of their hours. "
        "It is the stretch the team pays for a milestone, not a medical measure. In the world, a person who stays "
        "there loses productivity and may fall sick.")
    add("")
    add("### What the ablations say")
    add("")
    add(f"- **The go-live gate is where incidents go.** Without it the engine ships {ng['productionIncidents']} "
        f"pipelines that fail in production instead of {e['productionIncidents']}, customer escalations go from "
        f"{e['customerEscalations']} to {ng['customerEscalations']} and margin falls from {_pct(e['marginShare'], 1)} "
        f"to {_pct(ng['marginShare'], 1)}, because every incident costs rework hours and a penalty.")
    add(f"- **The escalation agent costs a little delivery and buys money.** Without it milestones on plan are "
        f"{_pct(ne['milestonesOnPlan'], 1)} against {_pct(e['milestonesOnPlan'], 1)}, but surprise slips rise from "
        f"{e['surpriseSlips']} to {ne['surpriseSlips']} and margin drops to {_pct(ne['marginShare'], 1)}: scope "
        f"creep that nobody turned into a change request is unpaid work.")
    add(f"- **Templates pay back.** Without them milestones on plan fall to {_pct(np_['milestonesOnPlan'], 1)} and "
        f"margin to {_pct(np_['marginShare'], 1)}.")
    add(f"- **Saying no is part of the job.** The engine that accepts every opportunity earns the most this year "
        f"({_pct(na['marginShare'], 1)} margin, utilization {_pct(na['utilization'], 1)}) and slips half its "
        f"milestones ({_pct(na['milestonesOnPlan'], 1)} on plan, {na['surpriseSlips']} surprise slips, "
        f"{na['customerEscalations']} customer escalations). The intake rule declined {e['engagementsDeclined']} "
        f"opportunities worth {_eur(e['declinedFeeEur'])}. That trade is the manager's call; the engine shows it "
        f"before the contract is signed.")
    add(f"- **The baselines are honest.** Staffing the first free person of the right profile reaches "
        f"{_pct(ff['milestonesOnPlan'], 1)} on plan with {ff['productionIncidents']} incidents.")
    add("")
    add("### The gate, written before any result")
    add("")
    add("`config/gate.json` was written before the first evaluation and is not moved. Dev:")
    add("")
    lines.extend(_gate_block(gate, dev))
    add("")
    add("## Held-out year")
    add("")
    if held is None:
        add("Not run yet. `python -m fde.eval.cli heldout` runs it once and writes `config/heldout.lock`.")
    else:
        lock = json.loads((root / "config/heldout.lock").read_text(encoding="utf-8"))
        he = held["designs"]["engine"]
        hb = held["designs"]["by_hand"]
        add(f"Run once on {lock['ranOn']}, on a year nothing was tuned on: {_world_line(held['world'])}. "
            "It is harder than dev: more opportunities, more public-sector and air-gapped work, more blockers, "
            "larger overruns and a thinner advisory bench. The lock records the hash of every config file it ran "
            "with. What happened and what changed afterwards is in [docs/heldout.md](docs/heldout.md).")
        add("")
        add(f"Engine {_pct(he['milestonesOnPlan'], 1)} milestones on plan against {_pct(hb['milestonesOnPlan'], 1)} "
            f"by hand, {he['productionIncidents']} production incidents against {hb['productionIncidents']}.")
        add("")
        lines.extend(_table(held))
        add("")
        lines.extend(_gate_block(gate, held))
    add("")
    add("## What is in it")
    add("")
    add("**Staffing planner** (`fde/product/staffing.py`). deepset's FDE team works in four profiles: Advisory "
        "for discovery, Builder for the build, Operating for go-live, Support for hypercare. The planner places "
        "people by expected hours of progress: profile fit, a penalty for missing skills (German, clearance, "
        "air-gapped experience, connectors) and a ramp-up cost for anyone new to the engagement. It aims to finish a "
        "phase a week early with a safety margin, keeps people near the utilization target, lets a person stretch "
        "to a full week only when a milestone is at stake and not two weeks in a row, and fills idle builder hours "
        "with template work.")
    add("")
    add("**Escalation agent** (`fde/product/escalation.py`). A model reads each weekly status note, German or "
        "English, and returns signals: blocker, data access, scope change, sentiment, percent done. The model "
        "only reads. Code decides: a weighted score over the signals and the forecast, with a kind "
        "(unblock, change request, relationship, capacity) that tells the manager which call to make. The note text "
        "is data and never instructions. Without an API key a bilingual keyword reader does the same job.")
    add("")
    add("**Go-live gate** (`fde/product/gate.py`). Before a customer RAG pipeline ships, the gate builds it in "
        "Haystack (DocumentSplitter, InMemoryDocumentStore, InMemoryBM25Retriever and an extractive answerer) with "
        f"the customer's own configuration, runs {product['gate']['goldenQuestions']} golden questions, and "
        f"measures retrieval recall (at least {_pct(product['gate']['minRecall'])}) and grounded answers (at least "
        f"{_pct(product['gate']['minGrounded'])}). It also lints the topology: an external generator endpoint in "
        "an air-gapped deployment is a hard stop.")
    add("")
    add("**Patterns from the field** (`fde/product/patterns.py`). When the same piece of work (a SharePoint connector, "
        "PII redaction, packaging a model for an air-gapped install) has been built on "
        f"{product['patterns']['templateAfterEngagements']} engagements, it becomes a template and a product "
        "request. Later engagements do that work faster.")
    add("")
    add("**Intake** (`fde/product/intake.py`). Before an opportunity is accepted, its hours are spread to their due "
        "dates on top of the work already planned. If any profile would run above its share of capacity over the "
        "next weeks, the engine declines and says which profile is short.")
    add("")
    add("**Service** (`fde/service/app.py`). FastAPI with API keys and roles (manager, FDE), an append-only "
        "hash-chained audit log in memory or Postgres, Prometheus counters at `/metrics`, and the console.")
    add("")
    add("**Console** (`web/`). React, TypeScript and Framer Motion. Engagements riskiest first with the escalation "
        "verdict on a new note, the week's staffing board, go-live reviews that run the gate, and the results. Every "
        "screen has loading, error and empty states.")
    add("")
    add("![The staffing board for the week](docs/console-team.png)")
    add("")
    add("![A go-live review that held back a pipeline](docs/console-review.png)")
    add("")
    add("## How it is kept honest")
    add("")
    add("- The truth stays in the world. `fde/world` knows how fast each person really works, what a blocker "
        "really is and which pipeline will fail in production. `fde/product` and `fde/service` never import it; "
        "a test checks.")
    add("- The world does not read the product's settings. `config/world.json` is read only by `fde/world`, "
        "`config/product.json` only by the product.")
    add("- Same luck for every design. Every random draw is keyed by what it is about (seed, week, engagement, "
        "person), not by the order of calls, so a design that does something different does not change the luck "
        "of anything else.")
    add("- The model reads and code decides.")
    add("- The gate was written before the first result, and the held-out year runs once.")
    add("- This README is generated by `python -m fde.eval.cli readme`. CI regenerates it and fails if it differs.")
    add("")
    add("## Run it")
    add("")
    add("```bash")
    add("python -m venv .venv && . .venv/bin/activate")
    add("pip install -r requirements.txt")
    add("pytest -q tests                      # the Python tests")
    add("python -m fde.eval.cli evaluate      # the dev year, writes reports/dev.json")
    add("python -m fde.eval.cli gate          # checks it against config/gate.json")
    add("python -m fde.eval.cli readme        # writes this file")
    add("uvicorn fde.service.app:app --port 8790")
    add("cd web && npm ci && npm run dev       # the console on :5173")
    add("```")
    add("")
    add("Or `docker build -t fde-delivery-engine . && docker run -p 8790:8790 fde-delivery-engine` and open "
        "http://localhost:8790. Set `ANTHROPIC_API_KEY` to read status notes with Claude, and `DATABASE_URL` "
        "to keep the audit log in Postgres.")
    add("")
    add("## Limits")
    add("")
    add("- The year is simulated. The rates, the profiles and the kinds of work come from public material about "
        "forward-deployed teams and Haystack deployments; the people, customers and pipelines are invented.")
    add("- The gate measures retrieval and extractive answers with BM25. A real deployment would add the "
        "customer's generator and embedding retrieval to the same golden questions.")
    add("- The planner plans one week at a time. It does not optimise the whole quarter.")
    add("")
    return "\n".join(lines)
