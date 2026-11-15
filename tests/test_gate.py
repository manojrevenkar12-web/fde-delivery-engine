from fde.config import load
from fde.product import gate as g

CATALOG, PRODUCT = load("catalog.json"), load("product.json")

DOCS = [g.SourceDoc(f"p{i}", f"Förderprogramm Thema{i} Süd ist ein Angebot des Referats Umwelt. Anträge für "
                    f"Förderprogramm Thema{i} Süd sind bis zum {i + 1}. März einzureichen. Die Förderhöhe für "
                    f"Förderprogramm Thema{i} Süd liegt bei bis zu {i + 2}.500 Euro.", "Umwelt" if i % 2 else "Bauen")
        for i in range(20)]
QUESTIONS = [g.GoldenQuestion(f"Bis wann sind Anträge für Förderprogramm Thema{i} Süd einzureichen?", f"{i + 1}. März",
                              f"p{i}") for i in range(20)]
GOOD = g.PipelineConfig(60, 10, 5, None, "http://llm.inference.svc.cluster.local:8080/v1", 2)


def test_a_healthy_pipeline_passes():
    r = g.review(GOOD, "air_gapped", DOCS, QUESTIONS, PRODUCT, CATALOG)
    assert r.passed and r.recall == 1.0 and r.grounded == 1.0


def test_tiny_chunks_and_a_wrong_filter_are_blocked_with_the_reason():
    tiny = g.PipelineConfig(6, 0, 5, None, GOOD.generator_endpoint, 2)
    r = g.review(tiny, "self_hosted", DOCS, QUESTIONS, PRODUCT, CATALOG)
    assert not r.passed and any("recall" in f for f in r.findings)
    filtered = g.PipelineConfig(60, 10, 5, "Bauen", GOOD.generator_endpoint, 2)
    r = g.review(filtered, "self_hosted", DOCS, QUESTIONS, PRODUCT, CATALOG)
    assert not r.passed and r.recall <= 0.5


def test_an_air_gapped_pipeline_must_not_call_out():
    out = g.PipelineConfig(60, 10, 5, None, "https://api.openai.com/v1", 2)
    r = g.review(out, "air_gapped", DOCS, QUESTIONS, PRODUCT, CATALOG)
    assert not r.passed and "outside an air-gapped network" in r.findings[0]
    assert g.review(out, "cloud", DOCS, QUESTIONS, PRODUCT, CATALOG).passed


def test_a_missing_document_shows_up_as_a_miss():
    r = g.review(GOOD, "cloud", DOCS[1:], QUESTIONS, PRODUCT, CATALOG)
    assert r.recall == 0.95 and QUESTIONS[0].question in r.misses


def test_sentences_keep_german_dates_and_chunks_are_stitched():
    from haystack import Document
    chunks = [Document(content="Anträge sind bis zum 17. ", meta={"doc_id": "a", "split_idx_start": 0}),
              Document(content="zum 17. Dezember einzureichen.", meta={"doc_id": "a", "split_idx_start": 17})]
    assert g.stitch(chunks) == [("a", "Anträge sind bis zum 17. Dezember einzureichen.")]
    out = g.ExtractiveAnswerer().run(query="Bis wann sind Anträge einzureichen?", documents=chunks)
    assert out["answer"] == "Anträge sind bis zum 17. Dezember einzureichen." and out["source_id"] == "a"
