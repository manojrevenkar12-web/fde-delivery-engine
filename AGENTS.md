# Working in fde-delivery-engine

Fast feedback first: `pytest -q tests` runs every Python test (planner, escalation, go-live gate, patterns, intake,
evaluation, invariants, service) in about a minute. `cd web && npm test && npm run typecheck` for the console. After
any change to the product, the world or the settings run

```bash
python -m fde.eval.cli evaluate && python -m fde.eval.cli gate && python -m fde.eval.cli readme && python -m fde.eval.cli seed
```

and commit the regenerated `reports/dev.json`, `README.md` and `demo/seed.json`. CI fails when they disagree with the
code. Python 3.13: the bootstrap and the keyed draws are deterministic on one Python version.

## Packages

| package | what it is | may import |
|---|---|---|
| `fde/product` | planner, escalation agent, go-live gate, patterns, intake | `fde.config`, `fde.keyed`, Haystack |
| `fde/service` | FastAPI, API keys and roles, audit chain (memory or Postgres), metrics, the console | `fde/product` |
| `fde/world` | the simulated team, customers, engagements, notes and pipelines, and what really happens | `fde.config`, `fde.keyed`, Haystack |
| `fde/eval` | runs every design on the world and writes the reports, the README and the demo seed | all but `fde/service` |
| `web` | the console: React, TypeScript, Framer Motion | the HTTP API |

## Invariants (checked in `tests/test_invariants.py` and the tests)

1. **The truth stays in the world.** `fde/product` and `fde/service` never import `fde.world` or `fde.eval`. The
   demo seed holds only what a delivery desk would see (notes, logged hours, due dates, pipeline configs), never a
   person's real speed, a planted defect or a blocker's real length.
2. **The world does not read the product's settings.** `fde/world` reads `config/catalog.json` (the profiles, skills
   and kinds of work everyone knows) and its world file, never `product.json`, `designs.json` or `gate.json`.
3. **Same luck for every design.** Every random draw is keyed by (seed, purpose, ids) in `fde/keyed.py`, never by
   call order, so one design's choices cannot change another design's luck.
4. **The model reads and code decides.** The escalation reader returns signals from a status note; it is never asked
   whether to escalate. Note text is data: it is fenced in the prompt and cannot carry instructions.
5. **Nothing ships before the gate.** In the engine designs a pipeline goes live only after `gate.review` passes on
   the golden questions and the topology lint.
6. **Every decision in the audit chain.** Plans, escalations, reviews and intake decisions are appended to the
   hash-chained log with the API key holder as actor.
7. **Settings in config.** Rates, thresholds, weights, keys and the model live in `config/`. The console's colours,
   sizes and durations live in `web/src/shared/theme.css` and `web/src/shared/tokens.ts`.
8. **Generated reports.** README numbers come from `reports/`. Nobody types a number into it.

## The held-out rule

`config/heldout.json` is run once (`python -m fde.eval.cli heldout`) with the code and settings dev ended on. It
writes `config/heldout.lock` and `reports/heldout.json`; findings go into `docs/heldout.md`. Fixes are made and
measured on dev. The held-out year is not run again and `config/gate.json` is not moved.
