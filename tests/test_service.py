import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("FDE_NO_APP", "1")

from fde.service.app import create_app  # noqa: E402

M = {"X-Api-Key": "manager-demo-key"}
F = {"X-Api-Key": "fde-demo-key"}


@pytest.fixture()
def client():
    return TestClient(create_app(database_url=""))


def test_keys_and_roles(client):
    assert client.get("/api/team").status_code == 401
    assert client.get("/api/team", headers={"X-Api-Key": "nope"}).status_code == 401
    assert client.get("/api/team", headers=F).status_code == 200
    assert client.post("/api/plan", headers=F).status_code == 403
    assert client.get("/healthz").json() == {"status": "ok"}


def test_the_plan_respects_the_target_and_never_two_hot_weeks(client):
    team = client.post("/api/plan", headers=M).json()
    for p in team["people"]:
        if p["hotStreak"] == 0:
            assert p["load"] <= team["target"] + 1e-9
        assert p["load"] <= 1.0
    again = client.post("/api/plan", headers=M).json()
    hot_before = {p["id"] for p in team["people"] if p["hotStreak"] > 0}
    for p in again["people"]:
        if p["id"] in hot_before:
            assert p["load"] <= again["target"] + 1e-9


def test_a_note_is_read_scored_and_escalated_with_reasons(client):
    rows = client.get("/api/engagements", headers=M).json()["engagements"]
    eid = next(r["id"] for r in rows if not r["done"])
    blocked = "Weekly status. Build is roughly 30% done. Still waiting for VPN access to the customer's cluster."
    client.post(f"/api/engagements/{eid}/notes", headers=F, json={"text": blocked})
    out = client.post(f"/api/engagements/{eid}/notes", headers=F,
                      json={"text": blocked + " The customer also wants answers over their Confluence space now."})
    body = out.json()
    assert out.status_code == 200 and body["signals"]["blocker"] and body["signals"]["scope_change"]
    assert body["decision"]["escalate"] and body["decision"]["reasons"]
    detail = client.get(f"/api/engagements/{eid}", headers=M).json()
    assert detail["escalatedWeek"] is not None and detail["notes"][-1]["by"] == "fde:f-builder-01"
    assert client.post(f"/api/engagements/{eid}/notes", headers=F, json={"text": ""}).status_code == 422


def test_go_live_review_blocks_a_broken_pipeline_and_passes_a_fixed_one(client):
    review = client.get("/api/reviews", headers=M).json()["reviews"][0]
    eid = review["engagementId"]
    bad = client.post(f"/api/reviews/{eid}/run", headers=M, json={"config": {"split_length": 8, "split_overlap": 0}})
    assert bad.status_code == 200 and not bad.json()["passed"] and bad.json()["findings"]
    good = client.post(f"/api/reviews/{eid}/run", headers=M,
                       json={"config": {"split_length": 60, "split_overlap": 10, "top_k": 5,
                                        "department_filter": None, "replicas": 2,
                                        "generator_endpoint": "http://llm.inference.svc.cluster.local:8080/v1"}})
    assert good.json()["passed"], good.json()
    assert client.post(f"/api/reviews/{eid}/run", headers=M, json={"config": {"top_k": 0}}).status_code == 422
    assert client.post("/api/reviews/NOPE/run", headers=M, json={}).status_code == 404


def test_intake_answers_with_its_numbers(client):
    phases = {p: {"scopedHours": h, "dueWeek": 40 + i * 3} for i, (p, h) in
              enumerate([("discovery", 40), ("build", 160), ("go_live", 40), ("hypercare", 24)])}
    out = client.post("/api/intake", headers=M, json={"id": "OPP1", "customer": "Landkreis Test", "phases": phases})
    assert out.status_code == 200 and set(out.json()["loadByProfile"]) >= {"builder", "advisory"}
    huge = {p: {"scopedHours": 4000, "dueWeek": 31 + i} for i, p in enumerate(phases)}
    assert not client.post("/api/intake", headers=M, json={"id": "OPP2", "customer": "X", "phases": huge}).json()["accept"]
    assert client.post("/api/intake", headers=M, json={"id": "OPP3", "customer": "X", "phases": {}}).status_code == 422


def test_audit_trail_metrics_patterns_and_results(client):
    client.post("/api/plan", headers=M)
    assert client.get("/api/audit/verify", headers=M).json()["intact"]
    assert "fde_planned_utilization" in client.get("/metrics").text
    assert client.get("/api/patterns", headers=F).status_code == 200
    assert client.get("/api/results", headers=M).json()["dev"]["designs"]["engine"]


@pytest.mark.skipif(not os.environ.get("FDE_TEST_DATABASE_URL"), reason="needs Postgres")
def test_the_audit_trail_on_postgres():
    url = os.environ["FDE_TEST_DATABASE_URL"]
    c = TestClient(create_app(database_url=url))
    c.post("/api/plan", headers=M)
    c.post("/api/plan", headers=M)
    v = c.get("/api/audit/verify", headers=M).json()
    assert v["intact"] and v["entries"] >= 2
