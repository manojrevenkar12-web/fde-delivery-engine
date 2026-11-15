"""The go-live gate: run the customer's pipeline, as configured and indexed, against their golden questions.

The pipeline is real Haystack: the documents are split as configured, indexed in a document store, retrieved with
BM25 and answered extractively, so the gate measures exactly what would ship. It blocks go-live below the bar and on
any topology violation, and says why, so the fix is specific.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from haystack import Document, Pipeline, component
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

_WORD = re.compile(r"\w{3,}", re.UNICODE)
_STOP = frozenset("""the and for are was were with that this from must under what which when who how much many
does have has will can into than then there their about after before please der die das und für ist sind wie
wann welche welcher welches bis zum zur ein eine einer des dem den mit von bei liegt""".split())
# A sentence ends at . ! or ? after a letter, so German dates ("17. Dezember") and amounts stay whole.
_SENTENCE = re.compile(r"(?<=[^\W\d_][.!?])\s+")


@dataclass(frozen=True)
class PipelineConfig:
    split_length: int
    split_overlap: int
    top_k: int
    department_filter: str | None
    generator_endpoint: str
    replicas: int

    @staticmethod
    def from_json(m: dict[str, Any]) -> "PipelineConfig":
        return PipelineConfig(int(m["split_length"]), int(m["split_overlap"]), int(m["top_k"]),
                              m.get("department_filter"), str(m["generator_endpoint"]), int(m["replicas"]))

    def to_json(self) -> dict[str, Any]:
        return {"split_length": self.split_length, "split_overlap": self.split_overlap, "top_k": self.top_k,
                "department_filter": self.department_filter, "generator_endpoint": self.generator_endpoint,
                "replicas": self.replicas}


@dataclass(frozen=True)
class SourceDoc:
    id: str
    content: str
    department: str


@dataclass(frozen=True)
class GoldenQuestion:
    """A customer's question with the fact the answer must contain and the document that holds it."""

    question: str
    fact: str
    source_id: str


def stitch(chunks: list[Document]) -> list[tuple[str, str]]:
    """Joins the retrieved chunks of each document back into continuous text by their split offsets, so a sentence
    cut at a chunk boundary is whole again. Documents keep the rank of their best chunk."""
    order: list[str] = []
    parts: dict[str, list[Document]] = {}
    for c in chunks:
        doc_id = str(c.meta.get("doc_id", ""))
        if doc_id not in parts:
            order.append(doc_id)
            parts[doc_id] = []
        parts[doc_id].append(c)
    out: list[tuple[str, str]] = []
    for doc_id in order:
        text, end = "", -1
        for c in sorted(parts[doc_id], key=lambda d: int(d.meta.get("split_idx_start", 0))):
            start, content = int(c.meta.get("split_idx_start", 0)), c.content or ""
            if end < 0 or start >= end:
                text += (" " if text else "") + content
            else:
                text += content[end - start:]
            end = max(end, start + len(content))
        out.append((doc_id, text))
    return out


def terms(text: str) -> set[str]:
    """Content words, lower-cased and lightly stemmed, so "attached" meets "attach" and "Anträge" meets "Antrag"."""
    out = set()
    for w in _WORD.findall(text.lower()):
        if w in _STOP:
            continue
        for suffix in ("ed", "es", "en", "er", "e", "s"):
            if len(w) > 5 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.add(w)
    return out


@component
class ExtractiveAnswerer:
    """Answers with the retrieved sentence that shares the most words with the question; ties go to the higher rank.
    It stands in for the generator so the gate can measure grounding without a model."""

    @component.output_types(answer=str, source_id=str)
    def run(self, query: str, documents: list[Document]) -> dict[str, str]:
        q = terms(query)
        best, best_score, source = "", 0, ""
        for doc_id, text in stitch(documents):
            for sentence in _SENTENCE.split(text):
                score = len(q & terms(sentence))
                if score > best_score:
                    best, best_score, source = sentence.strip(), score, doc_id
        return {"answer": best, "source_id": source}


def build_pipeline(config: PipelineConfig, documents: list[SourceDoc]) -> Pipeline:
    splitter = DocumentSplitter(split_by="word", split_length=config.split_length, split_overlap=config.split_overlap)
    # "doc_id", not "source_id": Haystack's splitter writes its own source_id into every chunk.
    docs = [Document(content=d.content, meta={"doc_id": d.id, "department": d.department}) for d in documents]
    chunks = splitter.run(documents=docs)["documents"] if docs else []
    store = InMemoryDocumentStore()
    store.write_documents(chunks)
    filters = None
    if config.department_filter:
        filters = {"field": "meta.department", "operator": "==", "value": config.department_filter}
    pipeline = Pipeline()
    pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=store, top_k=config.top_k,
                                                              filters=filters))
    pipeline.add_component("answerer", ExtractiveAnswerer())
    pipeline.connect("retriever.documents", "answerer.documents")
    return pipeline


@dataclass
class GateResult:
    passed: bool
    recall: float
    grounded: float
    questions: int
    findings: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {"passed": self.passed, "recall": self.recall, "grounded": self.grounded, "questions": self.questions,
                "findings": self.findings, "misses": self.misses}


def evaluate_pipeline(config: PipelineConfig, documents: list[SourceDoc],
                      questions: list[GoldenQuestion]) -> tuple[float, float, list[str]]:
    """Share of questions whose fact is in a retrieved chunk, share answered with it, and the questions missed."""
    pipeline = build_pipeline(config, documents)
    hit = grounded = 0
    misses: list[str] = []
    for q in questions:
        out = pipeline.run({"retriever": {"query": q.question}, "answerer": {"query": q.question}},
                           include_outputs_from={"retriever"})
        chunks = out["retriever"]["documents"]
        fact = q.fact.lower()
        if any(c.meta.get("doc_id") == q.source_id and fact in (c.content or "").lower() for c in chunks):
            hit += 1
        else:
            misses.append(q.question)
        answer = out["answerer"]
        if answer["source_id"] == q.source_id and fact in answer["answer"].lower():
            grounded += 1
    n = max(1, len(questions))
    return hit / n, grounded / n, misses


def _internal(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname or ""
    if host in ("localhost",) or host.endswith(".internal") or host.endswith(".svc.cluster.local"):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def lint_topology(config: PipelineConfig, topology: str, catalog: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Blocking findings and warnings for the deployment topology."""
    blocking: list[str] = []
    warnings: list[str] = []
    allows_external = catalog["topologies"][topology]["externalNetwork"]
    if not allows_external and not _internal(config.generator_endpoint):
        blocking.append(f"generator calls {urlparse(config.generator_endpoint).hostname}, outside an air-gapped network")
    if config.replicas < 2:
        warnings.append("a single replica: no rolling updates without downtime")
    if config.top_k < 3:
        warnings.append(f"top_k={config.top_k} leaves no room for a second relevant passage")
    return blocking, warnings


def review(config: PipelineConfig, topology: str, documents: list[SourceDoc], questions: list[GoldenQuestion],
           settings: dict[str, Any], catalog: dict[str, Any]) -> GateResult:
    gate = settings["gate"]
    recall, grounded, misses = evaluate_pipeline(config, documents, questions)
    blocking, warnings = lint_topology(config, topology, catalog)
    findings = list(blocking)
    if recall < gate["minRecall"]:
        findings.append(f"recall {recall:.0%} is below {gate['minRecall']:.0%}")
    if grounded < gate["minGrounded"]:
        findings.append(f"grounded answers {grounded:.0%} are below {gate['minGrounded']:.0%}")
    passed = not findings
    return GateResult(passed, round(recall, 4), round(grounded, 4), len(questions), findings + warnings, misses[:10])
