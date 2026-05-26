"""Read-side helpers for surfacing vault files in API responses.

Mirrors the Streamlit Dashboard's frontmatter parsing + doc-id matching
logic verbatim (see ``callimachus/ui/pages/2_Dashboard.py``) so behaviour is
preserved across the cutover. Engine code isn't a great home for these
because they're presentation-shaped (e.g. "first try filename prefix,
then frontmatter") — they belong with the API.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from callimachus.api.models import EntityCardOut
from callimachus.project import Project

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# Strip a trailing ``_e<digits>`` entity suffix when falling back to the
# filename for grouping. ``vault_writer`` emits files like ``{doc}_e0.md``,
# so the stem without that suffix is a reasonable doc-id guess when the
# frontmatter omits ``source_document``.
_ENTITY_SUFFIX_RE = re.compile(r"_e\d+$")


def read_frontmatter(path: Path) -> dict[str, Any]:
    """Return YAML frontmatter as a dict (empty dict on any failure).

    The dict guarantee matters: a vault file whose frontmatter parses to a
    list or scalar (hand-edited, malformed) would otherwise let
    ``.get(...)`` calls in callers raise ``AttributeError``. Always coerce
    non-mapping payloads to ``{}`` so the type signature does not lie.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        parsed = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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


def _doc_id_for(path: Path, meta: dict[str, Any]) -> str:
    """Pick the doc_id a vault file belongs to.

    Frontmatter wins; otherwise strip the ``_e<digits>`` entity suffix
    from the stem so ``alpha_e0.md`` and ``alpha_e1.md`` land in the same
    bucket. Same precedence as ``vault_files_for`` (frontmatter vs.
    filename prefix), just inverted.
    """
    src = meta.get("source_document")
    if isinstance(src, str) and src.strip():
        return src.strip()
    return _ENTITY_SUFFIX_RE.sub("", path.stem)


def list_vault_documents(project: Project) -> list[dict[str, Any]]:
    """Group the approved vault into per-document summaries.

    Returns one record per source document, with the entity count and
    the set of classes that appeared. Proposal markdowns live under
    ``vault_dir/proposals/`` (a sub-directory) and the top-level glob
    here ignores them — so this is naturally "approved entities only".
    """
    if not project.vault_dir.exists():
        return []
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"doc_id": None, "source_document": None, "entity_count": 0, "classes": set()}
    )
    for path in sorted(project.vault_dir.glob("*.md")):
        meta = read_frontmatter(path)
        doc_id = _doc_id_for(path, meta)
        bucket = buckets[doc_id]
        bucket["doc_id"] = doc_id
        bucket["source_document"] = meta.get("source_document") or doc_id
        bucket["entity_count"] += 1
        cls = meta.get("class")
        if cls:
            bucket["classes"].add(cls)
    return [
        {
            "doc_id": b["doc_id"],
            "source_document": b["source_document"],
            "entity_count": b["entity_count"],
            "classes": sorted(b["classes"]),
        }
        for b in buckets.values()
    ]


def read_vault_file(project: Project, filename: str) -> dict[str, Any] | None:
    """Return the full content of one vault markdown file.

    Returns ``None`` if the file is missing or escapes ``vault_dir``.
    The split between frontmatter (parsed) and body (raw markdown) keeps
    the wire shape friendly for the React viewer's properties-table +
    react-markdown rendering split.
    """
    vault_dir = project.vault_dir.resolve()
    candidate = (vault_dir / filename).resolve()
    try:
        candidate.relative_to(vault_dir)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if m:
        try:
            parsed = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            parsed = None
        frontmatter = parsed if isinstance(parsed, dict) else {}
        body = text[m.end():]
    else:
        frontmatter = {}
        body = text
    return {"filename": candidate.name, "frontmatter": frontmatter, "body": body}
