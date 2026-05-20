"""Shape-only smoke tests for the FastAPI surface.

Goal: every endpoint returns 200/201/204/404 (as appropriate) and the body
matches the response model. We don't assert on engine behaviour here —
that's covered (or not) by engine-level tests.

Run:
    pytest tests/api -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from callimachus.api.main import create_app


@pytest.fixture(scope="module")
def client():
    # ``with`` is required so FastAPI's lifespan fires and JobRegistry
    # lands on ``app.state``.
    with TestClient(create_app()) as c:
        yield c


def test_list_projects_returns_list(client: TestClient) -> None:
    r = client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    # Both shipped projects should be present in a fresh checkout.
    names = {p["name"] for p in body}
    assert {"compliance", "thematic"}.issubset(names), names


def test_list_project_templates(client: TestClient) -> None:
    r = client.get("/api/projects/templates")
    assert r.status_code == 200
    templates = r.json()
    assert isinstance(templates, list)
    names = {t["name"] for t in templates}
    assert "compliance" in names


def test_project_detail_compliance(client: TestClient) -> None:
    r = client.get("/api/projects/compliance")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "compliance"
    assert body["pack"]["name"]
    assert isinstance(body["pack"]["classes"], list)
    assert len(body["pack"]["classes"]) >= 1


def test_project_detail_unknown_returns_404(client: TestClient) -> None:
    r = client.get("/api/projects/does_not_exist_xyz")
    assert r.status_code == 404


def test_project_pack_includes_cq_sparql(client: TestClient) -> None:
    r = client.get("/api/projects/compliance/pack")
    assert r.status_code == 200
    body = r.json()
    cqs = body["competency_questions"]
    # The compliance pack ships at least one CQ with a .rq file alongside.
    if cqs:
        # At least one CQ should have the SPARQL inlined.
        assert any(cq.get("sparql") for cq in cqs)


def test_settings_shape(client: TestClient) -> None:
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["api_key_set"], bool)
    assert body["repo_root"]
    assert body["projects_dir"]


def test_cache_clear(client: TestClient) -> None:
    r = client.post("/api/settings/cache/clear")
    assert r.status_code == 200
    assert r.json() == {"cleared": True}


def test_job_unknown_returns_404(client: TestClient) -> None:
    r = client.get("/api/jobs/no_such_job_id")
    assert r.status_code == 404


def test_schema_preview(client: TestClient) -> None:
    r = client.post(
        "/api/projects/compliance/schema/preview",
        json={
            "doc_id": "regression_doc",
            "text": "§2 Interpretation. \"data controller\" means a person.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["system"]
    assert body["user"]
    # The doc_id placeholder must have been substituted somewhere in
    # the rendered prompts (compliance pack uses {doc_id}).
    assert "regression_doc" in body["system"] + body["user"]


def test_tool_schema_shape(client: TestClient) -> None:
    r = client.get("/api/projects/compliance/schema/tool-schema")
    assert r.status_code == 200
    body = r.json()
    # Mirrors what extractor.call_llm passes to Anthropic as input_schema.
    assert "schema" in body
    schema = body["schema"]
    assert schema["type"] == "object"
    assert "entities" in schema["properties"]
