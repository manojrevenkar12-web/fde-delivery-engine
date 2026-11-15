"""The pipelines teams build, with the defects tired or mismatched builders leave in them, and how they really do in
production. The world runs production traffic with Haystack itself, separately from the product's gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from haystack import Document
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from fde.world import corpus
from fde.world.world import Job, World

GOOD = {"split_length": 60, "split_overlap": 10, "top_k": 5, "department_filter": None, "replicas": 2}


@dataclass
class Deployment:
    config: dict[str, Any]
    documents: list[corpus.Doc]
    golden: list[corpus.Question]
    production: list[corpus.Question]
    defects: list[str]


def build(w: World, job: Job, builders: list[str]) -> Deployment:
    """The pipeline as the team leaves it at the end of build, defects included."""
    p = w.cfg["pipelines"]
    fatigue = max([w.person(b).fatigue for b in builders] or [0])
    mismatch = any(not job.required <= w.person(b).skills for b in builders)
    chance = p["defectBase"] + p["defectPerFatigue"] * fatigue + (p["defectSkillMismatch"] if mismatch else 0)
    defects: list[str] = []
    if w.k.chance(min(0.9, chance), "defect", job.id):
        kinds = {k: v for k, v in p["defects"].items() if k != "external_endpoint" or job.topology == "air_gapped"}
        total, u, acc = sum(kinds.values()), w.k.u("defectKind", job.id), 0.0
        for kind, weight in kinds.items():
            acc += weight / total
            if u < acc:
                defects.append(kind)
                break
    progs = w.corpus_for(job)
    docs = [corpus.document(pr, job.german) for pr in progs]
    config = dict(GOOD)
    internal = "http://llm.inference.svc.cluster.local:8080/v1"
    config["generator_endpoint"] = internal if job.topology != "cloud" else "https://api.mistral.ai/v1"
    if "stale_index" in defects:
        docs = [d for i, d in enumerate(docs) if not w.k.chance(0.25, "stale", job.id, i)]
    if "small_chunks" in defects:
        config["split_length"], config["split_overlap"] = 8, 0
    if "top_k_one" in defects:
        config["top_k"] = 1
    if "wrong_filter" in defects:
        config["department_filter"] = progs[0].department
    if "external_endpoint" in defects:
        config["generator_endpoint"] = "https://api.openai.com/v1"
    golden = corpus.questions(w.k, progs, job.german, p["goldenQuestions"], f"golden-{job.id}")
    production = corpus.questions(w.k, progs, job.german, p["productionQuestions"], f"prod-{job.id}")
    return Deployment(config, docs, golden, production, defects)


def production_recall(dep: Deployment) -> float:
    """Share of real users' questions whose answer passage is retrieved, on the pipeline as deployed."""
    c = dep.config
    splitter = DocumentSplitter(split_by="word", split_length=c["split_length"], split_overlap=c["split_overlap"])
    chunks = splitter.run(documents=[Document(content=d.content, meta={"sid": d.id, "dept": d.department})
                                     for d in dep.documents])["documents"]
    store = InMemoryDocumentStore()
    store.write_documents(chunks)
    filters = None
    if c["department_filter"]:
        filters = {"field": "meta.dept", "operator": "==", "value": c["department_filter"]}
    retriever = InMemoryBM25Retriever(document_store=store, top_k=c["top_k"], filters=filters)
    hits = 0
    for q in dep.production:
        found = retriever.run(query=q.question)["documents"]
        if any(d.meta.get("sid") == q.source_id and q.fact.lower() in (d.content or "").lower() for d in found):
            hits += 1
    return hits / max(1, len(dep.production))


def fails_in_production(w: World, job: Job, dep: Deployment) -> bool:
    if "external_endpoint" in dep.defects:
        return True
    return production_recall(dep) < w.cfg["pipelines"]["productionRecallFloor"]
