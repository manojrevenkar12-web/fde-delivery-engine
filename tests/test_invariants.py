"""The invariants in AGENTS.md, checked on the source tree."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sources(package):
    return list((ROOT / "fde" / package).rglob("*.py"))


def offenders(package, pattern):
    rx = re.compile(pattern)
    return [str(p.relative_to(ROOT)) for p in sources(package) if rx.search(p.read_text(encoding="utf-8"))]


def test_nothing_that_serves_reads_the_truth():
    bad = offenders("product", r"(from|import) fde\.(world|eval)") + offenders("service", r"(from|import) fde\.(world|eval)")
    assert not bad, bad


def test_the_world_does_not_read_the_products_settings_or_code():
    assert not offenders("world", r"fde\.product|product\.json|designs\.json|gate\.json")


def test_the_model_is_asked_for_signals_never_for_a_verdict():
    text = (ROOT / "fde/product/escalation.py").read_text(encoding="utf-8")
    prompt = text[text.index("def prompt"):text.index("def read(self, note")]
    assert not re.search(r"(?i)should (we|i) escalate|decide|verdict", prompt)


def test_the_demo_seed_holds_no_truth():
    seed = ROOT / "demo" / "seed.json"
    if seed.exists():
        text = seed.read_text(encoding="utf-8")
        for word in ("true_hours", "productivity", "fatigue", "defects", "production"):
            assert f'"{word}"' not in text, word
