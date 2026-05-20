"""Query router smoke tests.

The sync endpoints (sparql, run-cq, rebuild-ttl) hit real engine code
against the shipped vault. The NL-ask job patches the three pipeline
calls so we never reach out to the real LLM provider — the
test exercises the JobRegistry contract and the orchestrator's progress
events, not the LLM.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from callimachus.api.main import create_app
from callimachus.api.models import NLAnswerOut


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def test_rebuild_ttl(client: TestClient) -> None:
    r = client.post("/api/projects/compliance/query/rebuild-ttl")
    assert r.status_code == 200
    body = r.json()
    assert body["rebuilt"] is True
    assert body["size_bytes"] > 0


def test_run_sparql_select(client: TestClient) -> None:
    r = client.post(
        "/api/projects/compliance/query/sparql",
        json={
            "sparql": (
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
                "SELECT ?s ?label WHERE { ?s rdfs:label ?label } LIMIT 5"
            )
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "select"
    assert "rows" in body
    assert isinstance(body["variables"], list)


def test_run_sparql_invalid(client: TestClient) -> None:
    r = client.post(
        "/api/projects/compliance/query/sparql",
        json={"sparql": "this is not sparql"},
    )
    assert r.status_code == 400


def test_run_competency_question(client: TestClient) -> None:
    # cq1 is the obligations query; ships in every compliance build.
    r = client.post(
        "/api/projects/compliance/query/competency-questions/cq1/run"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cq_id"] == "cq1"
    assert body["sparql"]
    assert body["result"]["kind"] in {"select", "ask", "graph"}


def test_run_competency_question_unknown(client: TestClient) -> None:
    r = client.post(
        "/api/projects/compliance/query/competency-questions/nope/run"
    )
    assert r.status_code == 404


def test_nl_ask_without_api_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post(
        "/api/projects/compliance/query/ask",
        json={"question": "anything"},
    )
    assert r.status_code == 400


def test_nl_ask_job_orchestration(client: TestClient, monkeypatch) -> None:
    """The job should kick, stream stage events, and land NLAnswerOut.

    We patch the three engine calls so the test runs offline — the
    orchestrator's contract (which events fire and what the terminal
    result looks like) is what we're locking in.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_results = {
        "kind": "select",
        "variables": ["s"],
        "rows": [{"s": "<urn:fake>"}],
    }

    with patch(
             "callimachus.api.routers.query.ask_engine.synthesize_sparql",
             return_value=("SELECT * WHERE { ?s ?p ?o }", "test rationale"),
         ), \
         patch(
             "callimachus.api.routers.query.ask_engine.run_sparql",
             return_value=fake_results,
         ), \
         patch(
             "callimachus.api.routers.query.ask_engine.summarise",
             return_value="**Test answer** with [citation](vault/x.md).",
         ):
        r = client.post(
            "/api/projects/compliance/query/ask",
            json={"question": "smoke?", "model": "test-model"},
        )
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        # Poll until terminal — the BackgroundTask runs in a worker
        # thread, so the snapshot endpoint may need a moment.
        for _ in range(50):
            snap = client.get(f"/api/jobs/{job_id}").json()
            if snap["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert snap["status"] == "done", snap

    # Stages from the orchestrator should all be present.
    messages = [e["message"] for e in snap["progress"]]
    assert any("Synthesising" in m for m in messages), messages
    assert any("Executing" in m for m in messages), messages
    assert any("Summarising" in m for m in messages), messages

    # Terminal result validates against NLAnswerOut.
    out = NLAnswerOut.model_validate(snap["result"])
    assert out.question == "smoke?"
    assert out.sparql.startswith("SELECT")
    assert out.result.kind == "select"
    assert "Test answer" in out.answer
