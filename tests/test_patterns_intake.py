from fde.config import load
from fde.product import intake
from fde.product.model import Engagement, EngagementState, Fde, PhaseScope
from fde.product.patterns import PatternLibrary

CATALOG, PRODUCT = load("catalog.json"), load("product.json")


def test_recurring_custom_work_becomes_a_template_that_saves_hours():
    lib = PatternLibrary.from_config(PRODUCT, CATALOG)
    lib.record("E1", ("sharepoint_connector", "ocr_scanned_pdfs"))
    assert lib.queued == []
    lib.record("E2", ("sharepoint_connector",))
    assert lib.queued == ["sharepoint_connector"]
    before = lib.build_hours(("sharepoint_connector",))
    lib.built("sharepoint_connector")
    assert lib.build_hours(("sharepoint_connector",)) == before * (1 - CATALOG["templateSavingShare"])
    assert lib.product_requests()[0] == {"workType": "sharepoint_connector", "engagements": 2, "templated": True}


def eng(eid, start, scale=1.0):
    phases = {"discovery": PhaseScope(int(40 * scale), start + 3), "build": PhaseScope(int(200 * scale), start + 9),
              "go_live": PhaseScope(int(48 * scale), start + 12), "hypercare": PhaseScope(int(32 * scale), start + 14)}
    return Engagement(eid, "K", "public", "cloud", "tm", 1, start, phases, frozenset(), ())


def test_intake_says_no_when_a_profile_would_be_overloaded():
    roster = [Fde(f"f-{p}-1", p, p, frozenset(), 40) for p in ("advisory", "builder", "operating", "support")]
    assert intake.decide(0, eng("E1", 0), [], roster, CATALOG, PRODUCT).accept
    busy = [EngagementState(eng(f"B{i}", 0, 1.5), "build") for i in range(3)]
    d = intake.decide(0, eng("E9", 0), busy, roster, CATALOG, PRODUCT)
    assert not d.accept and "builder" in d.reason
