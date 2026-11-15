import json
from pathlib import Path

from fde.config import ROOT, load
from fde.eval import gate
from fde.world.world import World


def small(seed):
    cfg = json.loads((ROOT / "config/world.json").read_text())
    cfg["seed"], cfg["weeks"] = seed, 20
    return World(cfg, load("catalog.json"))


def test_the_same_seed_makes_the_same_world():
    a, b = small("s1"), small("s1")
    assert [(j.id, j.scoped, j.true_hours) for j in a.jobs] == [(j.id, j.scoped, j.true_hours) for j in b.jobs]
    assert [p.skills for p in a.people] == [p.skills for p in b.people]
    assert [j.true_hours for j in small("s2").jobs] != [j.true_hours for j in a.jobs]


def test_the_gate_reads_the_report_and_fails_a_bad_one():
    report = json.loads((ROOT / "reports/dev.json").read_text())
    g = json.loads((ROOT / "config/gate.json").read_text())
    assert len(gate.check(g, report)["lines"]) >= 8
    report["designs"]["engine"]["productionIncidents"] = 9
    assert not gate.check(g, report)["passed"]
