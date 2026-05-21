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
    assert "literature" in names
    assert "regulatory" in names



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
    # Every shipped provider should appear with a boolean `configured`.
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1
    provider_ids = {p["id"] for p in body["providers"]}
    assert {"anthropic", "openai", "gemini"}.issubset(provider_ids)
    for p in body["providers"]:
        assert isinstance(p["configured"], bool)
        assert p["env_var"].endswith("_API_KEY")


def test_update_pack_models_rejects_builtin(client: TestClient) -> None:
    # The shipped `compliance` project uses the built-in pack; mutating
    # it should return 400, not silently overwrite the package files.
    r = client.patch(
        "/api/projects/compliance/pack/models",
        json={"extractor": "openai/gpt-4o-mini"},
    )
    assert r.status_code == 400
    assert "built-in" in r.json()["detail"].lower()


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
    # Mirrors what extractor.call_llm passes to litellm as tool parameters.
    assert "schema" in body
    schema = body["schema"]
    assert schema["type"] == "object"
    assert "entities" in schema["properties"]


def test_builtin_packs_validation() -> None:
    from callimachus.pack import load_builtin
    # Test that both new packs load successfully and validate against Pydantic models.
    lit_pack = load_builtin("literature")
    assert lit_pack.metadata.name == "literature"
    assert "Paper" in lit_pack.class_names
    assert "Claim" in lit_pack.class_names

    reg_pack = load_builtin("regulatory")
    assert reg_pack.metadata.name == "regulatory"
    assert "Filing" in reg_pack.class_names
    assert "Issuer" in reg_pack.class_names

