"""Tests for triples_to_dot and the /graph HTTP endpoint."""
from __future__ import annotations

from pathlib import Path

import pytest

from callimachus.api.vault_view import all_vault_files, triples_to_dot


# ---------- triples_to_dot unit tests ----------------------------------------

def test_triples_to_dot_empty_returns_valid_digraph() -> None:
    dot = triples_to_dot([], pack_classes=[], vault_files=[])
    assert dot.startswith("digraph vault {")
    assert dot.endswith("}")


def test_triples_to_dot_rdf_type_sets_node_color() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=["Obligation"], vault_files=[])
    assert "#4c6ef5" in dot  # first palette color assigned to first class


def test_triples_to_dot_rdfs_label_used_as_display_label() -> None:
    triples = [
        '<http://ex.org/PersonalData> <http://www.w3.org/2000/01/rdf-schema#label>'
        ' "Personal Data" .',
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "Personal Data" in dot


def test_triples_to_dot_non_type_predicate_becomes_edge() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://ex.org/pack#hasController>"
        " <http://ex.org/Controller> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "->" in dot
    assert "hasController" in dot


def test_triples_to_dot_rdf_type_not_rendered_as_edge() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    # rdf:type is encoded as node colour, NOT as an arrow
    assert "->" not in dot


def test_triples_to_dot_vault_filename_as_node_id(tmp_path: Path) -> None:
    vault_file = tmp_path / "personal_data_e0.md"
    vault_file.write_text("---\nclass: Obligation\n---\n", encoding="utf-8")
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[vault_file])
    # The node ID is the URL-encoded vault filename
    assert "personal_data_e0.md" in dot


def test_triples_to_dot_typed_literal_skipped() -> None:
    """Typed-literal data properties (e.g., age^^xsd:integer) must not produce edges."""
    triples = [
        '<http://ex.org/Alice> <http://ex.org/age>'
        ' "42"^^<http://www.w3.org/2001/XMLSchema#integer> .',
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "->" not in dot
    assert "integer" not in dot


def test_triples_to_dot_blank_node_subject_skipped() -> None:
    """Triples with blank-node subjects must be silently skipped."""
    triples = [
        "_:b0 <http://ex.org/p> <http://ex.org/Y> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "->" not in dot


def test_all_vault_files_returns_md_files(tmp_path: Path, monkeypatch) -> None:
    import callimachus.api.deps as api_deps
    import callimachus.project.project as pm
    from callimachus.project import create_from_template

    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(pm, "projects_dir", lambda: projects_root)
    api_deps.clear_project_cache()
    project = create_from_template("avf_test", template="thematic", backend="filesystem")
    project.vault_dir.mkdir(parents=True, exist_ok=True)
    (project.vault_dir / "alpha_e0.md").write_text("---\n---\n", encoding="utf-8")
    (project.vault_dir / "beta_e0.md").write_text("---\n---\n", encoding="utf-8")

    files = all_vault_files(project)
    assert len(files) == 2
    assert all(f.suffix == ".md" for f in files)
    api_deps.clear_project_cache()
