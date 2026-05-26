"""Smoke tests for the vault browser router.

Scaffolds a thematic-template project in ``tmp_path``, writes a couple
of fake vault markdown files directly (no curator round-trip), and
exercises the list / detail / single-file endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import callimachus.api.deps as api_deps
import callimachus.project.project as project_module
from callimachus.api.main import create_app
from callimachus.project import create_from_template


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(project_module, "projects_dir", lambda: projects_root)
    api_deps.clear_project_cache()
    project = create_from_template("test_vault", template="thematic", backend="filesystem")
    yield project
    api_deps.clear_project_cache()


@pytest.fixture
def client(isolated_project):
    with TestClient(create_app()) as c:
        yield c


def _write_entity(
    project, filename: str, *, cls: str, label: str, source_document: str, body: str = "body"
) -> None:
    project.vault_dir.mkdir(parents=True, exist_ok=True)
    (project.vault_dir / filename).write_text(
        "---\n"
        f"class: {cls}\n"
        f"label: {label}\n"
        f"source_document: {source_document}\n"
        "source_page: 3\n"
        "source_text: a representative excerpt\n"
        "---\n"
        f"{body}\n",
        encoding="utf-8",
    )


def test_vault_list_empty(client: TestClient) -> None:
    r = client.get("/api/projects/test_vault/vault")
    assert r.status_code == 200
    assert r.json() == {"documents": []}


def test_vault_list_groups_by_doc_id_via_filename_prefix(
    client: TestClient, isolated_project
) -> None:
    """Files share a doc when their filenames share the slug prefix."""
    _write_entity(isolated_project, "alpha_e0.md", cls="Code", label="A", source_document="alpha")
    _write_entity(isolated_project, "alpha_e1.md", cls="Code", label="B", source_document="alpha")
    _write_entity(isolated_project, "beta_e0.md", cls="Theme", label="C", source_document="beta")

    r = client.get("/api/projects/test_vault/vault")
    assert r.status_code == 200
    docs = {d["doc_id"]: d for d in r.json()["documents"]}
    assert set(docs.keys()) == {"alpha", "beta"}
    assert docs["alpha"]["entity_count"] == 2
    assert docs["alpha"]["classes"] == ["Code"]
    assert docs["beta"]["entity_count"] == 1
    assert docs["beta"]["classes"] == ["Theme"]


def test_vault_list_ignores_proposals_subdir(
    client: TestClient, isolated_project
) -> None:
    """Proposal markdowns live under ``vault/proposals/`` — must not appear."""
    _write_entity(
        isolated_project, "alpha_e0.md", cls="Code", label="A", source_document="alpha"
    )
    proposals_dir = isolated_project.vault_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    (proposals_dir / "proposal_abcdef12_merge.md").write_text(
        "---\nproposal_id: proposal_abcdef12\noperation: merge_entities\n---\nx\n",
        encoding="utf-8",
    )

    r = client.get("/api/projects/test_vault/vault")
    assert r.status_code == 200
    docs = r.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "alpha"


def test_vault_document_detail_returns_entity_cards(
    client: TestClient, isolated_project
) -> None:
    _write_entity(isolated_project, "alpha_e0.md", cls="Code", label="Alpha-0", source_document="alpha")
    _write_entity(isolated_project, "alpha_e1.md", cls="Code", label="Alpha-1", source_document="alpha")

    r = client.get("/api/projects/test_vault/vault/documents/alpha")
    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"] == "alpha"
    assert body["source_document"] == "alpha"
    labels = sorted(e["label"] for e in body["entities"])
    assert labels == ["Alpha-0", "Alpha-1"]
    assert all(e["cls"] == "Code" for e in body["entities"])


def test_vault_document_detail_404_when_missing(client: TestClient) -> None:
    r = client.get("/api/projects/test_vault/vault/documents/ghost")
    assert r.status_code == 404


def test_vault_file_returns_frontmatter_and_body(
    client: TestClient, isolated_project
) -> None:
    _write_entity(
        isolated_project,
        "alpha_e0.md",
        cls="Code",
        label="Alpha-0",
        source_document="alpha",
        body="## Heading\n\nSome body text.",
    )
    r = client.get("/api/projects/test_vault/vault/files/alpha_e0.md")
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "alpha_e0.md"
    assert body["frontmatter"]["class"] == "Code"
    assert body["frontmatter"]["label"] == "Alpha-0"
    assert body["frontmatter"]["source_page"] == 3
    assert "## Heading" in body["body"]


def test_vault_file_rejects_traversal(client: TestClient) -> None:
    # FastAPI's path-param pattern blocks any ``/`` or ``\\`` before the
    # handler sees it. The 422 (validation) is the expected shield.
    r = client.get("/api/projects/test_vault/vault/files/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in (404, 422)
    r = client.get("/api/projects/test_vault/vault/files/notes.txt")
    # ``.txt`` fails the ``\.md$`` constraint
    assert r.status_code == 422


def test_vault_file_404_for_missing(client: TestClient) -> None:
    r = client.get("/api/projects/test_vault/vault/files/nope_e0.md")
    assert r.status_code == 404
