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


def test_intake_counts_the_people_who_have_the_skills_the_work_needs():
    roster = [Fde("f-advisory-1", "a", "advisory", frozenset({"german"}), 40),
              Fde("f-advisory-2", "b", "advisory", frozenset(), 40),
              Fde("f-advisory-3", "c", "advisory", frozenset(), 40),
              *[Fde(f"f-{p}-1", p, p, frozenset({"german"}), 40) for p in ("builder", "operating", "support")]]

    def discovery_heavy(eid, skills):
        phases = {"discovery": PhaseScope(150, 3), "build": PhaseScope(8, 20), "go_live": PhaseScope(8, 22),
                  "hypercare": PhaseScope(8, 24)}
        return Engagement(eid, "K", "public", "cloud", "tm", 1, 0, phases, frozenset(skills), ())

    def german(eid):
        return discovery_heavy(eid, {"german"})

    def plain(eid):
        return discovery_heavy(eid, ())

    busy = [EngagementState(german(f"G{i}"), "discovery") for i in range(3)]
    d = intake.decide(0, german("G9"), busy, roster, CATALOG, PRODUCT)
    assert not d.accept and "advisory with german" in d.reason
    busy_plain = [EngagementState(plain(f"P{i}"), "discovery") for i in range(3)]
    assert intake.decide(0, plain("P9"), busy_plain, roster, CATALOG, PRODUCT).accept
