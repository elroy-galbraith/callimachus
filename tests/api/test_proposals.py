"""Smoke tests for the proposals router.

Pattern matches test_dashboard.py: scaffold an isolated thematic-template
project under tmp_path, then exercise the endpoints. The consolidator
and apply jobs both patch their respective engine entry points so we
don't hit the LLM or do disruptive vault mutations.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

import callimachus.api.deps as api_deps
import callimachus.project.project as project_module
from callimachus.api.main import create_app
from callimachus.engine.consolidator import Proposal
from callimachus.engine.proposal_applier import ApplyResult
from callimachus.project import create_from_template


def _seed_vault_entity(vault_dir: Path, name: str, **meta) -> Path:
    """Drop a stub vault file so the consolidator + apply have something to chew on."""
    vault_dir.mkdir(parents=True, exist_ok=True)
    full = {
        "id": name,
        "class": meta.pop("cls", "Code"),
        "label": meta.pop("label", name.replace("_", " ").title()),
        "source_document": meta.pop("source_document", "fake_doc"),
        "source_section": meta.pop("source_section", "§1"),
        "source_text": meta.pop("source_text", f"text for {name}"),
        **meta,
    }
    frontmatter = yaml.dump(full, sort_keys=False)
    path = vault_dir / f"{name}.md"
    path.write_text(f"---\n{frontmatter}---\n\nbody\n")
    return path


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(project_module, "projects_dir", lambda: projects_root)
    api_deps.clear_project_cache()
    project = create_from_template("test_proposals", template="thematic", backend="filesystem")
    # Pre-seed three Codes the consolidator could conceivably merge.
    _seed_vault_entity(project.vault_dir, "code_lack_transparency", cls="Code")
    _seed_vault_entity(project.vault_dir, "code_feeling_shut_out", cls="Code")
    _seed_vault_entity(project.vault_dir, "code_unclear_decisions", cls="Code")
    yield project
    api_deps.clear_project_cache()


@pytest.fixture
def client(isolated_project):
    with TestClient(create_app()) as c:
        yield c


def test_list_proposals_empty(client: TestClient) -> None:
    r = client.get("/api/projects/test_proposals/proposals")
    assert r.status_code == 200
    body = r.json()
    assert body["proposals"] == []
    # All five status buckets should be present (each 0).
    assert set(body["counts"].keys()) >= {
        "pending", "approved", "rejected", "deferred", "applied"
    }


def test_consolidator_job_writes_proposals(
    client: TestClient, isolated_project, monkeypatch
) -> None:
    """Mock the engine consolidate() to return one of each operation type.

    The job orchestrator should then write four proposal files and the
    list endpoint should surface them with DOT strings + payload summaries.
    """
    fake_proposals = [
        Proposal(
            operation="merge_entities",
            rationale="they describe the same construct",
            confidence="high",
            evidence=["text for code_lack_transparency"],
            payload={
                "kept_id": "code_lack_transparency",
                "removed_id": "code_feeling_shut_out",
            },
        ),
        Proposal(
            operation="group_codes",
            rationale="three codes share a theme",
            confidence="medium",
            evidence=["text for code_unclear_decisions"],
            payload={
                "new_subtheme_label": "Opacity",
                "parent_theme_id": "theme_governance",
                "member_code_ids": [
                    "code_lack_transparency",
                    "code_unclear_decisions",
                ],
            },
        ),
        Proposal(
            operation="link_hierarchy",
            rationale="missing structural link",
            confidence="medium",
            evidence=["text"],
            payload={
                "from_id": "theme_governance",
                "property": "hasSubtheme",
                "to_id": "subtheme_opacity",
            },
        ),
        Proposal(
            operation="rename_label",
            rationale="label too wordy",
            confidence="low",
            evidence=["text for code_lack_transparency"],
            payload={
                "entity_id": "code_lack_transparency",
                "new_label": "Transparency Gap",
            },
        ),
    ]

    with patch(
        "callimachus.api.routers.proposals.run_consolidator_engine",
        return_value=fake_proposals,
    ):
        r = client.post("/api/projects/test_proposals/proposals/run")
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            snap = client.get(f"/api/jobs/{job_id}").json()
            if snap["status"] in ("done", "error"):
                break
            time.sleep(0.05)
    assert snap["status"] == "done", snap
    assert snap["result"]["proposals_written"] == 4

    r = client.get("/api/projects/test_proposals/proposals")
    assert r.status_code == 200
    body = r.json()
    proposals = body["proposals"]
    assert len(proposals) == 4
    ops = {p["operation"] for p in proposals}
    assert ops == {
        "merge_entities", "group_codes", "link_hierarchy", "rename_label"
    }
    # All should start pending
    assert all(p["status"] == "pending" for p in proposals)
    assert body["counts"]["pending"] == 4
    # DOT strings should be populated
    assert all(p["dot"] for p in proposals)
    # Payloads should be re-nested under "payload"
    merge = next(p for p in proposals if p["operation"] == "merge_entities")
    assert merge["payload"]["kept_id"] == "code_lack_transparency"
    assert merge["payload"]["removed_id"] == "code_feeling_shut_out"


def test_patch_proposal_status(client: TestClient, isolated_project) -> None:
    # Manually drop a proposal file so we don't need the consolidator.
    proposals_dir = isolated_project.vault_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    pid = "proposal_deadbeef"
    fm = yaml.dump({
        "proposal_id": pid,
        "operation": "rename_label",
        "status": "pending",
        "confidence": "low",
        "entity_id": "code_x",
        "new_label": "Better Label",
        "rationale": "wordy",
        "evidence": ["text"],
    }, sort_keys=False)
    (proposals_dir / f"{pid}_rename_code_x.md").write_text(f"---\n{fm}---\n\nbody\n")

    r = client.patch(
        f"/api/projects/test_proposals/proposals/{pid}",
        json={"status": "approved", "reviewer_notes": "Looks right"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["reviewer_notes"] == "Looks right"


def test_patch_proposal_unknown_404(client: TestClient) -> None:
    # Valid id format (8 hex chars) but no such file → 404.
    r = client.patch(
        "/api/projects/test_proposals/proposals/proposal_cafebabe",
        json={"status": "approved"},
    )
    assert r.status_code == 404


def test_patch_proposal_malformed_id_422(client: TestClient) -> None:
    # The proposal_id path-param regex rejects glob-style ids before
    # the route runs.
    r = client.patch(
        "/api/projects/test_proposals/proposals/proposal_nope",
        json={"status": "approved"},
    )
    assert r.status_code == 422


def test_get_project_rejects_non_snake_case_name(client: TestClient) -> None:
    # The {name} path-param regex blocks anything that isn't snake_case
    # (defence-in-depth against path traversal — capital letters or dots
    # in the URL would otherwise reach ``load_project``).
    for bad in ("Compliance", "compliance.bak", "compli-ance"):
        r = client.get(f"/api/projects/{bad}")
        assert r.status_code == 422, (bad, r.status_code)


def test_patch_proposal_bad_status_400(client: TestClient, isolated_project) -> None:
    # Pydantic catches the bad literal before the route runs — 422.
    proposals_dir = isolated_project.vault_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump({
        "proposal_id": "proposal_aaaaaaaa",
        "operation": "rename_label",
        "status": "pending",
        "confidence": "low",
        "entity_id": "x",
        "new_label": "y",
        "rationale": "",
        "evidence": [],
    }, sort_keys=False)
    (proposals_dir / "proposal_aaaaaaaa_rename_x.md").write_text(f"---\n{fm}---\n\nbody\n")
    r = client.patch(
        "/api/projects/test_proposals/proposals/proposal_aaaaaaaa",
        json={"status": "not_a_real_status"},
    )
    assert r.status_code == 422


def test_apply_job_runs_through_results(
    client: TestClient, isolated_project, monkeypatch
) -> None:
    """The apply job should emit one event per ApplyResult and store them."""
    fake_results = [
        ApplyResult(
            proposal_id="proposal_aaaa",
            operation="rename_label",
            ok=True,
            message="renamed code_x",
            touched=["code_x.md"],
        ),
        ApplyResult(
            proposal_id="proposal_bbbb",
            operation="merge_entities",
            ok=False,
            message="conflict: kept_id missing",
            touched=[],
        ),
    ]
    with patch(
        "callimachus.api.routers.proposals.apply_approved",
        return_value=fake_results,
    ):
        r = client.post("/api/projects/test_proposals/proposals/apply")
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            snap = client.get(f"/api/jobs/{job_id}").json()
            if snap["status"] in ("done", "error"):
                break
            time.sleep(0.05)
    assert snap["status"] == "done", snap
    res = snap["result"]
    assert res["succeeded"] == 1
    assert res["failed"] == 1
    assert {r["proposal_id"] for r in res["results"]} == {
        "proposal_aaaa", "proposal_bbbb"
    }
    # Should have emitted one event per result + at least one header event.
    msgs = [e["message"] for e in snap["progress"]]
    assert any("ok: rename_label" in m for m in msgs), msgs
    assert any("failed: merge_entities" in m for m in msgs), msgs
