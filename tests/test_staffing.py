from fde.config import load
from fde.product.model import Assignment, Engagement, EngagementState, Fde, PhaseScope, Plan
from fde.product.staffing import StaffingSettings, hot_streaks, plan_week

CATALOG = load("catalog.json")
PRODUCT = load("product.json")
SETTINGS = StaffingSettings.from_config(PRODUCT)


def fde(i, profile, skills=("german",), cap=40):
    return Fde(f"f-{profile}-{i}", f"P{i}", profile, frozenset(skills), cap)


def engagement(eid, due_build=10, build=160, skills=("german",), start=0):
    phases = {"discovery": PhaseScope(40, 2), "build": PhaseScope(build, due_build), "go_live": PhaseScope(40, 14),
              "hypercare": PhaseScope(24, 16)}
    return Engagement(eid, "Kunde", "public", "self_hosted", "tm", 100000, start, phases, frozenset(skills), ())


def state(e, phase="build"):
    return EngagementState(e, phase)


def test_stays_inside_the_utilization_target():
    roster = [fde(1, "builder"), fde(2, "builder")]
    states = [state(engagement("E1", due_build=3, build=400))]
    plan = plan_week(1, roster, {"f-builder-1": 40, "f-builder-2": 40}, states, None, {}, [], SETTINGS, CATALOG)
    for f in roster:
        assert plan.hours_of(f.id) <= 40 * SETTINGS.utilization_target
    assert any("short" in w for w in plan.warnings)


def test_a_due_date_at_stake_may_stretch_someone_once_but_not_two_weeks_running():
    roster = [fde(1, "builder")]
    st = state(engagement("E1", due_build=2, build=400))
    avail = {"f-builder-1": 40}
    first = plan_week(1, roster, avail, [st], None, {}, [], SETTINGS, CATALOG)
    assert first.hours_of("f-builder-1") > 40 * SETTINGS.utilization_target
    hot = hot_streaks(first, avail, {}, SETTINGS.hot_load)
    assert hot["f-builder-1"] == 1
    second = plan_week(1, roster, avail, [st], first, hot, [], SETTINGS, CATALOG)
    assert second.hours_of("f-builder-1") <= 40 * SETTINGS.utilization_target


def test_keeps_people_on_their_engagements_and_matches_skills():
    roster = [fde(1, "builder", skills=()), fde(2, "builder", skills=("german",)), fde(3, "builder", skills=("german",))]
    st = state(engagement("E1", due_build=8, build=120))
    last = Plan(0, [Assignment("f-builder-3", "E1", "build", 24)], [])
    plan = plan_week(1, roster, {f.id: 40 for f in roster}, [st], last, {}, [], SETTINGS, CATALOG)
    on = {a.fde_id for a in plan.assignments if a.engagement_id == "E1"}
    assert "f-builder-3" in on, "the person already on it stays on it"
    assert "f-builder-1" not in on, "nobody without German on a German engagement while others are free"


def test_overdue_work_is_not_starved_by_newer_work():
    roster = [fde(1, "builder")]
    old = state(engagement("E1", due_build=3, build=200))
    new = state(engagement("E2", due_build=12, build=200, start=4))
    plan = plan_week(6, roster, {"f-builder-1": 40}, [new, old], None, {}, [], SETTINGS, CATALOG)
    assert plan.assignments[0].engagement_id == "E1"


def test_idle_builders_build_templates():
    roster = [fde(1, "builder")]
    plan = plan_week(1, roster, {"f-builder-1": 40}, [], None, {}, ["sharepoint_connector"], SETTINGS, CATALOG)
    assert plan.assignments and plan.assignments[0].engagement_id == "template:sharepoint_connector"


def test_reported_progress_reestimates_what_is_left():
    st = state(engagement("E1"))
    st.logged["build"] = 150
    assert st.remaining_estimate("build") == 10
    st.reported_done["build"] = 0.5
    assert st.remaining_estimate("build") == 150, "half done after 150h means 150h more, not 10"
