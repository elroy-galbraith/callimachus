"""Smoke tests for inbox + pending routers.

These tests scaffold a fresh project in ``tmp_path`` and monkeypatch the
``projects_dir`` lookup so we never touch the real compliance/thematic
inboxes on disk. The ``process`` job patches ``curator.process_pdf`` to
avoid hitting the LLM — we're verifying orchestration + job contract,
not the extractor.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import kgforge.api.deps as api_deps
import kgforge.project.project as project_module
from kgforge.api.main import create_app
from kgforge.approval.base import Submission, SubmissionRef
from kgforge.project import create_from_template


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """Scaffold a thematic-template project under tmp_path/projects/."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(project_module, "projects_dir", lambda: projects_root)
    # `load_project` cache lives across tests; nuke it both before and
    # after so nothing leaks back into the real `compliance`/`thematic`
    # projects.
    api_deps.clear_project_cache()
    project = create_from_template("test_inbox", template="thematic", backend="filesystem")
    yield project
    api_deps.clear_project_cache()


@pytest.fixture
def client(isolated_project):
    with TestClient(create_app()) as c:
        yield c


def test_inbox_empty_then_upload_then_clear(client: TestClient) -> None:
    # Empty to start
    r = client.get("/api/projects/test_inbox/inbox")
    assert r.status_code == 200
    body = r.json()
    assert body["files"] == []
    assert ".txt" in body["accepted_extensions"] or ".pdf" in body["accepted_extensions"]

    # Upload a .txt (thematic accepts .txt/.md/.vtt/.pdf)
    payload = b"Speaker A: alpha beta gamma\n" * 200  # ~5KB
    r = client.post(
        "/api/projects/test_inbox/inbox/upload",
        files={"files": ("sample.txt", payload, "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["saved"]) == 1
    assert body["saved"][0]["name"] == "sample.txt"
    assert body["saved"][0]["is_text_like"] is True
    assert body["saved"][0]["n_chars"] is not None

    # Now it appears in the listing
    r = client.get("/api/projects/test_inbox/inbox")
    files = r.json()["files"]
    assert {f["name"] for f in files} == {"sample.txt"}

    # Clear it
    r = client.delete("/api/projects/test_inbox/inbox")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1

    # Empty again
    r = client.get("/api/projects/test_inbox/inbox")
    assert r.json()["files"] == []


def test_upload_rejects_disallowed_extension(client: TestClient) -> None:
    r = client.post(
        "/api/projects/test_inbox/inbox/upload",
        files={"files": ("evil.exe", b"MZ\x00", "application/x-msdos-program")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["saved"] == []
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["name"] == "evil.exe"


def test_upload_strips_path_traversal(client: TestClient) -> None:
    """A filename with traversal segments should land as just the basename."""
    r = client.post(
        "/api/projects/test_inbox/inbox/upload",
        files={"files": ("../../etc/secrets.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 201
    saved = r.json()["saved"]
    assert len(saved) == 1
    assert saved[0]["name"] == "secrets.txt"


def test_process_empty_inbox_400(client: TestClient) -> None:
    r = client.post("/api/projects/test_inbox/inbox/process")
    assert r.status_code == 400


def test_process_job_orchestrates_per_file(
    client: TestClient, isolated_project, monkeypatch
) -> None:
    """The job should iterate files, emit per-file events, and persist a result.

    ``curator.process_pdf`` is patched to write a fake vault file + submit
    via the real approval backend so the pending queue gets populated.
    """
    inbox_dir = isolated_project.inbox_dir
    inbox_dir.mkdir(exist_ok=True)
    (inbox_dir / "a.txt").write_text("Speaker A: hello\nSpeaker B: world\n")
    (inbox_dir / "b.txt").write_text("Speaker A: second file\n")

    def fake_process_pdf(path, *, pack, vault_dir, sources_dir, approval, prompt_version="extractor-v1"):
        # Create a single fake vault file for this doc_id.
        doc_id = path.stem
        vault_file = vault_dir / f"{doc_id}_e0.md"
        vault_dir.mkdir(parents=True, exist_ok=True)
        vault_file.write_text(
            "---\n"
            f"class: Excerpt\n"
            f"id: {doc_id}_e0\n"
            f"label: Test entity {doc_id}\n"
            f"source_document: {doc_id}\n"
            f"source_text: hello world\n"
            "---\n"
            "body"
        )
        approval.submit(
            Submission(
                doc_id=doc_id,
                vault_files=[vault_file],
                pdf_path=path,
                pack_name=pack.metadata.name,
                prompt_version=prompt_version,
                model="test-model",
            )
        )

    with patch(
        "kgforge.api.routers.inbox.curator_engine.process_pdf",
        side_effect=fake_process_pdf,
    ):
        r = client.post("/api/projects/test_inbox/inbox/process")
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            snap = client.get(f"/api/jobs/{job_id}").json()
            if snap["status"] in ("done", "error"):
                break
            time.sleep(0.05)
    assert snap["status"] == "done", snap
    assert snap["result"]["processed"] == 2
    assert snap["result"]["succeeded"] == 2
    assert snap["result"]["failed"] == 0

    # Two pending submissions, each with one entity card
    r = client.get("/api/projects/test_inbox/pending")
    assert r.status_code == 200
    pending = r.json()
    assert {p["doc_id"] for p in pending} == {"a", "b"}
    for p in pending:
        assert p["backend"] == "filesystem"
        assert len(p["entities"]) == 1
        ec = p["entities"][0]
        assert ec["cls"] == "Excerpt"
        assert ec["label"].startswith("Test entity")

    # Approve one, reject one
    a = next(p for p in pending if p["doc_id"] == "a")
    b = next(p for p in pending if p["doc_id"] == "b")

    r = client.post(f"/api/projects/test_inbox/pending/{a['handle']}/approve")
    assert r.status_code == 204

    r = client.post(
        f"/api/projects/test_inbox/pending/{b['handle']}/reject",
        json={"reason": "smoke test"},
    )
    assert r.status_code == 204

    # Pending queue is now empty
    r = client.get("/api/projects/test_inbox/pending")
    assert r.json() == []


def test_pending_approve_unknown_handle(client: TestClient) -> None:
    r = client.post("/api/projects/test_inbox/pending/9999/approve")
    assert r.status_code == 404
