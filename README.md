# fde-delivery-engine

The delivery engine of a forward-deployed engineering team shipping Haystack into enterprise and public-sector production: staffing by FDE profile against utilization and burnout, a go-live gate that measures customer RAG pipelines, an escalation agent, and reusable patterns from the field.

It is written from the seat of the manager who runs that team. Every Monday the manager has the same questions: who works on what this week, which engagement is about to slip and needs a call to the customer, is this pipeline good enough to go live, which piece of work have we built twice and should turn into a template, and can we take the next opportunity without burning the team. This repository answers each one in code, and measures the answers on a simulated year of engagements before trusting them.

![The delivery desk: engagements, the escalation verdict on a status note](docs/console-engagements.png)

## Dashboard

Dev year: 52 weeks, 14 forward-deployed engineers, 47 opportunities (23 public sector, 9 finance, 11 insurance, 4 manufacturing, 7 air-gapped), seed `dev-2026`. Every design below runs on the same opportunities, the same people and the same luck.

| | Engine | Note |
|---|---:|---|
| Milestones on plan | **82%** | by hand 14% |
| Surprise slips | **11** | by hand 42 |
| Person-weeks above 90% load | **163** | by hand 461 |
| Production incidents | **0** | by hand 7 |
| Margin | **9.6%** | by hand -0.5% |
| Customer escalations | **5** | by hand 28 |
| Per-engagement gain in milestones on plan | **+63.5 pts** | paired bootstrap over 32 engagements, 90% interval 54.3 to 72.2 |
| Average team load | **73%** | by hand 72%, target 82% |
| Pipelines the gate held back | **6** | would have failed in production, 0 held back that would have passed |
| Templates built from repeated work | **8** | 1077 hours saved for 232 hours spent building them |
| Tests | **42** | 31 Python, 11 console |

### Every design on the dev year

| Design | Milestones on plan | Surprise slips | Customer escalations | Utilization | Person-weeks above 90% load | Production incidents | Margin | Declined |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Engine** | 82.0% | 11 | 5 | 72.3% | 163 | 0 | 9.6% | 12 |
| By hand (baseline) | 13.8% | 42 | 28 | 71.6% | 461 | 7 | -0.5% | 0 |
| First free person | 18.4% | 41 | 26 | 73.8% | 454 | 13 | -8.1% | 0 |
| Engine, no go-live gate | 82.7% | 10 | 12 | 72.3% | 157 | 7 | 5.5% | 12 |
| Engine, no escalation agent | 86.1% | 13 | 4 | 71.7% | 179 | 0 | 2.3% | 16 |
| Engine, no templates | 79.4% | 9 | 3 | 71.0% | 152 | 0 | 3.6% | 14 |
| Engine, accepts every opportunity | 53.0% | 34 | 15 | 81.1% | 234 | 0 | 21.9% | 0 |

"Person-weeks above 90% load" counts weeks in which one person was planned above 90% of their hours. It is the stretch the team pays for a milestone, not a medical measure. In the world, a person who stays there loses productivity and may fall sick.

### What the ablations say

- **The go-live gate is where incidents go.** Without it the engine ships 7 pipelines that fail in production instead of 0, customer escalations go from 5 to 12 and margin falls from 9.6% to 5.5%, because every incident costs rework hours and a penalty.
- **The escalation agent costs a little delivery and buys money.** Without it milestones on plan are 86.1% against 82.0%, but surprise slips rise from 11 to 13 and margin drops to 2.3%: scope creep that nobody turned into a change request is unpaid work.
- **Templates pay back.** Without them milestones on plan fall to 79.4% and margin to 3.6%.
- **Saying no is part of the job.** The engine that accepts every opportunity earns the most this year (21.9% margin, utilization 81.1%) and slips half its milestones (53.0% on plan, 34 surprise slips, 15 customer escalations). The intake rule declined 12 opportunities worth €1,024k. That trade is the manager's call; the engine shows it before the contract is signed.
- **The baselines are honest.** Staffing the first free person of the right profile reaches 18.4% on plan with 13 incidents.

### The gate, written before any result

`config/gate.json` was written before the first evaluation and is not moved. Dev:

```
pass milestones on plan                           0.8198 >= 0.8
pass milestone gain over the baseline, points     68.1 >= 10
pass surprise slips vs the baseline               0.262 <= 0.5
pass weeks above 90% load vs the baseline         0.354 <= 0.5
pass production incidents                         0 <= 1
pass utilization at least                         0.7227 >= 0.65
pass utilization at most                          0.7227 <= 0.88
pass margin share beats the baseline              0.0961 > -0.0052
GATE PASSED
```

## Held-out year

Run once on 2026-11-15, on a year nothing was tuned on: 52 weeks, 14 forward-deployed engineers, 60 opportunities (33 public sector, 12 finance, 5 insurance, 10 manufacturing, 21 air-gapped), seed `heldout-2027`. It is harder than dev: more opportunities, more public-sector and air-gapped work, more blockers, larger overruns and a thinner advisory bench. The lock records the hash of every config file it ran with. What happened and what changed afterwards is in [docs/heldout.md](docs/heldout.md).

Engine 56.8% milestones on plan against 7.6% by hand, 1 production incidents against 8.

| Design | Milestones on plan | Surprise slips | Customer escalations | Utilization | Person-weeks above 90% load | Production incidents | Margin | Declined |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Engine** | 56.8% | 19 | 14 | 60.2% | 164 | 1 | -19.2% | 35 |
| By hand (baseline) | 7.6% | 62 | 40 | 63.5% | 407 | 8 | -6.8% | 0 |
| First free person | 1.7% | 67 | 52 | 72.3% | 449 | 15 | -37.2% | 0 |
| Engine, no go-live gate | 56.2% | 20 | 18 | 60.5% | 165 | 4 | -21.9% | 35 |
| Engine, no escalation agent | 55.3% | 23 | 11 | 67.0% | 168 | 1 | -8.1% | 31 |
| Engine, no templates | 55.1% | 21 | 14 | 61.9% | 174 | 1 | -22.2% | 35 |
| Engine, accepts every opportunity | 15.2% | 78 | 48 | 84.0% | 284 | 1 | 19.3% | 0 |

```
FAIL milestones on plan                           0.5682 >= 0.8
pass milestone gain over the baseline, points     49.3 >= 10
pass surprise slips vs the baseline               0.306 <= 0.5
pass weeks above 90% load vs the baseline         0.403 <= 0.5
pass production incidents                         1 <= 1
FAIL utilization at least                         0.6016 >= 0.65
pass utilization at most                          0.6016 <= 0.88
FAIL margin share beats the baseline              -0.1925 > -0.0681
GATE FAILED
```

## What is in it

**Staffing planner** (`fde/product/staffing.py`). deepset's FDE team works in four profiles: Advisory for discovery, Builder for the build, Operating for go-live, Support for hypercare. The planner places people by expected hours of progress: profile fit, a penalty for missing skills (German, clearance, air-gapped experience, connectors) and a ramp-up cost for anyone new to the engagement. It aims to finish a phase a week early with a safety margin, keeps people near the utilization target, lets a person stretch to a full week only when a milestone is at stake and not two weeks in a row, and fills idle builder hours with template work.

**Escalation agent** (`fde/product/escalation.py`). A model reads each weekly status note, German or English, and returns signals: blocker, data access, scope change, sentiment, percent done. The model only reads. Code decides: a weighted score over the signals and the forecast, with a kind (unblock, change request, relationship, capacity) that tells the manager which call to make. The note text is data and never instructions. Without an API key a bilingual keyword reader does the same job.

**Go-live gate** (`fde/product/gate.py`). Before a customer RAG pipeline ships, the gate builds it in Haystack (DocumentSplitter, InMemoryDocumentStore, InMemoryBM25Retriever and an extractive answerer) with the customer's own configuration, runs 30 golden questions, and measures retrieval recall (at least 90%) and grounded answers (at least 85%). It also lints the topology: an external generator endpoint in an air-gapped deployment is a hard stop.

**Patterns from the field** (`fde/product/patterns.py`). When the same piece of work (a SharePoint connector, PII redaction, packaging a model for an air-gapped install) has been built on 2 engagements, it becomes a template and a product request. Later engagements do that work faster.

**Intake** (`fde/product/intake.py`). Before an opportunity is accepted, its hours are spread to their due dates on top of the work already planned. If any profile would run above its share of capacity over the next weeks, the engine declines and says which profile is short.

**Service** (`fde/service/app.py`). FastAPI with API keys and roles (manager, FDE), an append-only hash-chained audit log in memory or Postgres, Prometheus counters at `/metrics`, and the console.

**Console** (`web/`). React, TypeScript and Framer Motion. Engagements riskiest first with the escalation verdict on a new note, the week's staffing board, go-live reviews that run the gate, and the results. Every screen has loading, error and empty states.

![The staffing board for the week](docs/console-team.png)

![A go-live review that held back a pipeline](docs/console-review.png)

## How it is kept honest

- The truth stays in the world. `fde/world` knows how fast each person really works, what a blocker really is and which pipeline will fail in production. `fde/product` and `fde/service` never import it; a test checks.
- The world does not read the product's settings. `config/world.json` is read only by `fde/world`, `config/product.json` only by the product.
- Same luck for every design. Every random draw is keyed by what it is about (seed, week, engagement, person), not by the order of calls, so a design that does something different does not change the luck of anything else.
- The model reads and code decides.
- The gate was written before the first result, and the held-out year runs once.
- This README is generated by `python -m fde.eval.cli readme`. CI regenerates it and fails if it differs.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q tests                      # the Python tests
python -m fde.eval.cli evaluate      # the dev year, writes reports/dev.json
python -m fde.eval.cli gate          # checks it against config/gate.json
python -m fde.eval.cli readme        # writes this file
uvicorn fde.service.app:app --port 8790
cd web && npm ci && npm run dev       # the console on :5173
```

Or `docker build -t fde-delivery-engine . && docker run -p 8790:8790 fde-delivery-engine` and open http://localhost:8790. Set `ANTHROPIC_API_KEY` to read status notes with Claude, and `DATABASE_URL` to keep the audit log in Postgres.

## Limits

- The year is simulated. The rates, the profiles and the kinds of work come from public material about forward-deployed teams and Haystack deployments; the people, customers and pipelines are invented.
- The gate measures retrieval and extractive answers with BM25. A real deployment would add the customer's generator and embedding retrieval to the same golden questions.
- The planner plans one week at a time. It does not optimise the whole quarter.
