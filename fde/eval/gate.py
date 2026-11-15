"""Checks a report against the gate written before any result."""

from __future__ import annotations

from typing import Any


def check(gate: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    d = report["designs"][gate["design"]]
    b = report["designs"][gate["baseline"]]
    lines: list[str] = []
    ok = True

    def line(what: str, value: float, op: str, bound: float) -> None:
        nonlocal ok
        passed = {">=": value >= bound, "<=": value <= bound, ">": value > bound}[op]
        ok = ok and passed
        lines.append(f"{'pass' if passed else 'FAIL'} {what:44s} {value:g} {op} {bound:g}")

    line("milestones on plan", d["milestonesOnPlan"], ">=", gate["minMilestonesOnPlan"])
    line("milestone gain over the baseline, points", round(100 * (d["milestonesOnPlan"] - b["milestonesOnPlan"]), 1),
         ">=", gate["minMilestoneGainPoints"])
    line("surprise slips vs the baseline", round(d["surpriseSlips"] / max(1, b["surpriseSlips"]), 3), "<=",
         gate["maxSurpriseSlipShareOfBaseline"])
    line("weeks above 90% load vs the baseline", round(d["burnoutWeeks"] / max(1, b["burnoutWeeks"]), 3), "<=",
         gate["maxBurnoutWeeksShareOfBaseline"])
    line("production incidents", d["productionIncidents"], "<=", gate["maxProductionIncidents"])
    lo, hi = gate["utilizationBand"]
    line("utilization at least", d["utilization"], ">=", lo)
    line("utilization at most", d["utilization"], "<=", hi)
    if gate["marginMustBeatBaseline"]:
        line("margin share beats the baseline", d["marginShare"], ">", b["marginShare"])
    lines.append("GATE PASSED" if ok else "GATE FAILED")
    return {"passed": ok, "lines": lines}
