"""Customer corpora: funding programmes, policies and products, each with facts a question can ask about.

Names are built from shared word pools on purpose, so programmes look alike ("Grünflächen Süd" and "Grünflächen
Nord") and a retriever has to tell them apart. Every fact is tied to the document it comes from.
"""

from __future__ import annotations

from dataclasses import dataclass

from fde.keyed import Keyed

_DE = {
    "kind": ["Förderprogramm", "Richtlinie", "Zuschuss", "Sonderprogramm"],
    "topic": ["Grünflächen", "Wärmepumpen", "Digitalisierung", "Ladesäulen", "Barrierefreiheit", "Gründung",
              "Weiterbildung", "Hochwasserschutz", "Pflegeplätze", "Radwege"],
    "where": ["Süd", "Nord", "Mitte", "Ost", "West", "Plus", "Kompakt"],
    "dept": ["Umwelt", "Wirtschaft", "Soziales", "Bauen"],
    "proof": ["Kostenvoranschlag", "Meldebescheinigung", "Handelsregisterauszug", "Energieausweis", "Lageplan",
              "Steuerbescheid", "Mietvertrag", "Gutachten"],
    "months": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
               "November", "Dezember"],
}
_EN = {
    "kind": ["Policy", "Plan", "Cover", "Programme"],
    "topic": ["Fleet", "Cyber", "Liability", "Machinery", "Warranty", "Travel", "Property", "Supplier", "Pension",
              "Equipment"],
    "where": ["Basic", "Plus", "Pro", "Select", "Prime", "Lite", "Max"],
    "dept": ["Claims", "Underwriting", "Operations", "Finance"],
    "proof": ["purchase invoice", "incident report", "maintenance log", "police report", "service contract",
              "photo evidence", "audit certificate", "loss estimate"],
    "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"],
}


@dataclass(frozen=True)
class Doc:
    id: str
    content: str
    department: str


@dataclass(frozen=True)
class Question:
    question: str
    fact: str
    source_id: str


@dataclass(frozen=True)
class Programme:
    id: str
    name: str
    department: str
    deadline: str
    amount: str
    proof: str


def programmes(k: Keyed, key: str, german: bool, n: int) -> list[Programme]:
    pool = _DE if german else _EN
    out: list[Programme] = []
    names: set[str] = set()
    i = 0
    while len(out) < n:
        name = " ".join([pool["kind"][k.pick(len(pool["kind"]), "kind", key, i)],
                         pool["topic"][k.pick(len(pool["topic"]), "topic", key, i)],
                         pool["where"][k.pick(len(pool["where"]), "where", key, i)]])
        i += 1
        if name in names:
            continue
        names.add(name)
        day = k.between(1, 28, "day", key, i)
        month = pool["months"][k.pick(12, "month", key, i)]
        amount = f"{k.between(2, 95, 'amt', key, i)}.{k.between(100, 999, 'amt2', key, i)}"
        out.append(Programme(f"{key}-p{len(out):03d}", name, pool["dept"][k.pick(4, "dept", key, i)],
                             f"{day}. {month}" if german else f"{day} {month}",
                             amount + (" Euro" if german else " euros"),
                             pool["proof"][k.pick(len(pool["proof"]), "proof", key, i)]))
    return out


def document(p: Programme, german: bool) -> Doc:
    if german:
        text = (f"{p.name} ist ein Angebot des Referats {p.department}. Anträge für {p.name} sind bis zum "
                f"{p.deadline} einzureichen. Die Förderhöhe für {p.name} liegt bei bis zu {p.amount}. Für {p.name} "
                f"ist als Nachweis ein {p.proof} beizulegen. Rückfragen zu {p.name} beantwortet das Referat "
                f"{p.department}.")
    else:
        text = (f"{p.name} is run by the {p.department} team. Claims under {p.name} must be filed by {p.deadline}. "
                f"The maximum amount under {p.name} is {p.amount}. For {p.name} please attach a {p.proof}. "
                f"Questions about {p.name} go to the {p.department} team.")
    return Doc(p.id, text, p.department)


def question(k: Keyed, p: Programme, german: bool, key: str) -> Question:
    which = k.pick(3, "which", key)
    if german:
        q = [(f"Bis wann sind Anträge für {p.name} einzureichen?", p.deadline),
             (f"Wie hoch ist die Förderhöhe für {p.name}?", p.amount),
             (f"Welcher Nachweis ist für {p.name} beizulegen?", p.proof)][which]
    else:
        q = [(f"By when must claims under {p.name} be filed?", p.deadline),
             (f"What is the maximum amount under {p.name}?", p.amount),
             (f"Which document must be attached for {p.name}?", p.proof)][which]
    return Question(q[0], q[1], p.id)


def questions(k: Keyed, progs: list[Programme], german: bool, n: int, purpose: str) -> list[Question]:
    return [question(k, progs[k.pick(len(progs), purpose, i)], german, f"{purpose}-{i}") for i in range(n)]
