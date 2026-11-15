"""Weekly status notes as an engagement lead writes them: English or German, signals buried in ordinary sentences."""

from __future__ import annotations

from dataclasses import dataclass

from fde.world.world import Job, World


@dataclass(frozen=True)
class NoteTruth:
    blocker: bool
    data_access: bool
    scope_change: bool
    sentiment: int
    pct_done: float


def truth(w: World, job: Job, week: int) -> NoteTruth:
    phase = job.phase
    pct = min(0.99, job.progress[phase] / max(1.0, job.true_hours[phase]))
    pct = min(0.99, pct * (1 + w.cfg["people"]["progressOptimism"]))
    creep = any(at == week for at, _p, _e in job.pending_creep)
    sentiment = -1 if job.unhappy_weeks >= 1 else (1 if w.k.chance(0.25, "happy", job.id, week) else 0)
    blocker = job.blocker is not None
    return NoteTruth(blocker, blocker and job.blocker.data_access, creep, sentiment, round(pct, 2))


_DE = {
    "open": ["Kurzes Update zu {c}.", "Wochenstand {c}.", "Status {c}, KW {wk}."],
    "progress": ["Wir sind bei etwa {pct}% der Phase {phase}.", "Die Phase {phase} ist zu rund {pct}% erledigt."],
    "blocker_access": ["Wir warten noch auf den Zugang zum Index-Server des Kunden.",
                       "Die Freigabe für die Testdaten fehlt weiterhin, wir kommen nicht weiter."],
    "blocker": ["Wir sind blockiert, bis die Fachabteilung die Dokumente sortiert hat.",
                "Wir warten auf eine Entscheidung zur Zielarchitektur."],
    "creep": ["Der Kunde möchte zusätzlich eine Anbindung an das Dokumentenarchiv.",
              "Neue Anforderung: die Antworten sollen auch Tabellen aus den Berichten auswerten."],
    "negative": ["Der Projektleiter auf Kundenseite ist unzufrieden mit dem Tempo.",
                 "Es gibt Sorge beim Kunden wegen des Termins."],
    "positive": ["Sehr gutes Feedback aus der Fachabteilung, der Kunde ist zufrieden."],
    "neutral": ["Sonst keine Besonderheiten.", "Nächste Woche Abstimmung mit der IT."],
}
_EN = {
    "open": ["Quick update on {c}.", "Weekly status for {c}.", "{c}, week {wk}."],
    "progress": ["We are around {pct}% through {phase}.", "{phase} is roughly {pct}% done."],
    "blocker_access": ["Still waiting for VPN access to the customer's cluster.",
                       "No access to the document share yet, we cannot proceed with indexing."],
    "blocker": ["We are blocked until the customer's architecture board signs off.",
                "Waiting on the customer's team to clean up the source documents."],
    "creep": ["The customer also wants answers over their Confluence space now.",
              "New requirement from the business: citations must link to the page in the PDF."],
    "negative": ["Their programme lead is frustrated with the pace.", "Some concern on their side about the date."],
    "positive": ["Great feedback from the pilot users, the customer is happy."],
    "neutral": ["Nothing else to flag.", "Alignment call with their IT next week."],
}


def render(w: World, job: Job, week: int, t: NoteTruth) -> str:
    pool = _DE if job.german else _EN
    k = w.k

    def one(key: str, *salt: object) -> str:
        options = pool[key]
        return options[k.pick(len(options), "note-" + key, job.id, week, *salt)]

    phase = {"discovery": "Discovery", "build": "Build", "go_live": "Go-live", "hypercare": "Hypercare"}[job.phase]
    parts = [one("open").format(c=job.customer, wk=week + 1),
             one("progress").format(pct=int(round(t.pct_done * 100)), phase=phase)]
    if t.blocker:
        parts.append(one("blocker_access" if t.data_access else "blocker"))
    if t.scope_change:
        parts.append(one("creep"))
    if t.sentiment < 0:
        parts.append(one("negative"))
    elif t.sentiment > 0:
        parts.append(one("positive"))
    else:
        parts.append(one("neutral"))
    return " ".join(parts)
