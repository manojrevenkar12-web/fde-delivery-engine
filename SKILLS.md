# SKILLS.md

## Add a kind of field work

1. Add it to `workTypes` in `config/catalog.json` with the hours it takes without a template.
2. The world draws work items from that list, and `PatternLibrary` turns it into a template once it has been built on
   `patterns.templateAfterEngagements` engagements.
3. Run the evaluation. `templatesBuilt` and `hoursSavedByTemplates` in the README move. Margin should not fall.

## Add a check to the go-live gate

1. Add the finding to `lint_topology` or a measure to `evaluate_pipeline` in `fde/product/gate.py`, with a test in
   `tests/test_gate.py` that shows a healthy pipeline passing and a broken one held back.
2. If the world should produce that defect, add it to `pipelines.defects` in the world files and to
   `fde/world/pipelines.py`. Keep the defect out of `demo/seed.json`.
3. Run the evaluation. `blockedThatWouldHavePassed` must not rise: a gate that holds back good pipelines costs weeks.

## Change how status notes are read

Edit `AnthropicReader.prompt` and `KeywordReader` in `fde/product/escalation.py`. Keep the note inside the `<note>`
fence and ask only for signals. Add the German and the English phrasing to `tests/test_escalation.py`. The invariants
test fails if the prompt asks the model for a decision.

## Read notes with Claude

Set `ANTHROPIC_API_KEY` before starting the service. The model name, URL and token limit are in `config/product.json`
under `model`. Without a key the keyword reader is used.

## Tune the planner

Change `staffing` in `config/product.json`, run `evaluate` and `gate` on dev only, and commit the regenerated
reports. Leave a line in the commit message saying what the previous value was and why it moved.
