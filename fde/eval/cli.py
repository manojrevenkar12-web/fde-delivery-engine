"""python -m fde.eval.cli evaluate | gate | heldout | readme | seed\n\nevaluate runs the dev year and the stress year; gate judges dev; the held-out year runs once."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from fde.config import ROOT
from fde.eval import gate as gate_mod
from fde.eval.run import evaluate


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summary(report: dict) -> str:
    lines = []
    for k, d in report["designs"].items():
        lines.append(f"{k:22s} on plan {d['milestonesOnPlan']:.3f}  surprise {d['surpriseSlips']:3d}  util "
                     f"{d['utilization']:.3f}  burnout {d['burnoutWeeks']:4d}  incidents {d['productionIncidents']:2d}  "
                     f"margin {d['marginShare']:.3f}  cust-esc {d['customerEscalations']:3d}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    root = ROOT
    cmd = argv[0] if argv else "evaluate"
    if cmd == "evaluate":
        report = evaluate(root, "world.json", "dev")
        _write(root / "reports" / "dev.json", report)
        print(summary(report))
        stress = evaluate(root, "stress.json", "stress")
        _write(root / "reports" / "stress.json", stress)
        print("stress")
        print(summary(stress))
        return 0
    if cmd == "gate":
        verdict = gate_mod.check(json.loads((root / "config/gate.json").read_text()),
                                 json.loads((root / "reports/dev.json").read_text()))
        print("\n".join(verdict["lines"]))
        return 0 if verdict["passed"] else 1
    if cmd == "heldout":
        lock = root / "config" / "heldout.lock"
        if lock.exists():
            print("the held-out year was already run; it is run once", file=sys.stderr)
            return 2
        report = evaluate(root, "heldout.json", "heldout")
        _write(root / "reports" / "heldout.json", report)
        verdict = gate_mod.check(json.loads((root / "config/gate.json").read_text()), report)
        digest = hashlib.sha256("".join((root / "config" / f).read_text() for f in
                                        ("catalog.json", "product.json", "designs.json", "gate.json", "heldout.json"))
                                .encode()).hexdigest()
        _write(lock, {"ranOn": date.today().isoformat(), "configSha256": digest, "gatePassed": verdict["passed"],
                      "gateLines": verdict["lines"]})
        print(summary(report))
        print("\n".join(verdict["lines"]))
        return 0
    if cmd == "readme":
        from fde.eval.readme import render
        (root / "README.md").write_text(render(root), encoding="utf-8")
        return 0
    if cmd == "seed":
        from fde.eval.seed import build
        _write(root / "demo" / "seed.json", build(root))
        return 0
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
