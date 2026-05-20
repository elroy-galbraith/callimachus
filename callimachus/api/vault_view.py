"""Read-side helpers for surfacing vault files in API responses.

Mirrors the Streamlit Dashboard's frontmatter parsing + doc-id matching
logic verbatim (see ``callimachus/ui/pages/2_Dashboard.py``) so behaviour is
preserved across the cutover. Engine code isn't a great home for these
because they're presentation-shaped (e.g. "first try filename prefix,
then frontmatter") — they belong with the API.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from callimachus.api.models import EntityCardOut
from callimachus.project import Project

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def read_frontmatter(path: Path) -> dict[str, Any]:
    """Return YAML frontmatter as a dict (empty dict on any failure)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def vault_files_for(project: Project, doc_id: str) -> list[Path]:
    """Vault files belonging to ``doc_id``.

    Prefix match first (cheap), then a frontmatter scan for the
    ``source_document`` field as a fallback. Same precedence as the
    Streamlit Dashboard so a port doesn't subtly change which entities
    a reviewer sees.
    """
    by_prefix = sorted(project.vault_dir.glob(f"{doc_id}*.md"))
    if by_prefix:
        return by_prefix
    if not project.vault_dir.exists():
        return []
    return sorted(
        p
        for p in project.vault_dir.glob("*.md")
        if read_frontmatter(p).get("source_document") == doc_id
    )


def entity_card_from_path(path: Path) -> EntityCardOut:
    """Wrap a single vault markdown file as an entity card."""
    meta = read_frontmatter(path)
    return EntityCardOut(
        filename=path.name,
        cls=meta.get("class"),
        label=meta.get("label"),
        source_section=meta.get("source_section"),
        source_page=meta.get("source_page"),
        source_text=meta.get("source_text"),
        properties=meta.get("properties") or {},
    )
