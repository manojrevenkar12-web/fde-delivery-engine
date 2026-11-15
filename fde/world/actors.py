"""The model stand-in that reads status notes: right most of the time, with the misses real models make."""

from __future__ import annotations

from dataclasses import dataclass

from fde.world.notes import NoteTruth
from fde.world.world import World


@dataclass(frozen=True)
class ReadSignals:
    blocker: bool
    data_access: bool
    scope_change: bool
    sentiment: int
    pct_done: float | None


def read_note(w: World, truth: NoteTruth, job_id: str, week: int) -> ReadSignals:
    r = w.cfg["reader"]
    k = w.k
    blocker = truth.blocker and not k.chance(r["missBlocker"], "rd-blocker", job_id, week)
    blocker = blocker or k.chance(r["inventSignal"], "rd-inv-blocker", job_id, week)
    scope = truth.scope_change and not k.chance(r["missScopeChange"], "rd-scope", job_id, week)
    scope = scope or k.chance(r["inventSignal"], "rd-inv-scope", job_id, week)
    sentiment = truth.sentiment
    if sentiment != 0 and k.chance(r["missSentiment"], "rd-sent", job_id, week):
        sentiment = 0
    noise = (k.u("rd-pct", job_id, week) * 2 - 1) * r["pctNoise"]
    pct = max(0.0, min(0.99, truth.pct_done + noise))
    return ReadSignals(blocker, blocker and truth.data_access, scope, sentiment, round(pct, 2))
