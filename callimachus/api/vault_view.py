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
from urllib.parse import quote as _url_quote

from callimachus.api.models import EntityCardOut
from callimachus.project import Project

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# Strip a trailing ``_e<digits>`` entity suffix when falling back to the
# filename for grouping. ``vault_writer`` emits files like ``{doc}_e0.md``,
# so the stem without that suffix is a reasonable doc-id guess when the
# frontmatter omits ``source_document``.
_ENTITY_SUFFIX_RE = re.compile(r"_e\d+$")

_IRI_IN_TRIPLE_RE = re.compile(r"<([^>]+)>")
_LITERAL_IN_TRIPLE_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_NORMALIZE_RE = re.compile(r"[\s\-_]")

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

_CLASS_COLORS = [
    "#4c6ef5", "#f76707", "#2f9e44", "#e03131",
    "#1098ad", "#d6336c", "#7048e8", "#f08c00",
]


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


def _normalize_for_lookup(s: str) -> str:
    """Lowercase and strip spaces/hyphens/underscores for URI→filename matching."""
    return _NORMALIZE_RE.sub("", s).lower()


def _local_name(iri: str) -> str:
    """Extract the local name from an IRI (after the last # or /)."""
    return iri.rsplit("#", 1)[-1] if "#" in iri else iri.rsplit("/", 1)[-1]


def all_vault_files(project: Project) -> list[Path]:
    """All approved vault markdown files (top-level only; proposals subdir excluded)."""
    if not project.vault_dir.exists():
        return []
    return sorted(project.vault_dir.glob("*.md"))


def triples_to_dot(
    triples: list[str],
    pack_classes: list[str],
    vault_files: list[Path],
) -> str:
    """Convert stringified RDF triples to a Graphviz DOT string.

    DOT node IDs are URL-encoded vault filenames so the browser click
    handler can call ``decodeURIComponent`` on the SVG ``<title>`` element
    and pass the result straight to ``GET /vault/files/{filename}``.
    """
    # Build normalized-local-name → vault-filename lookup.
    local_to_file: dict[str, str] = {}
    for path in vault_files:
        stem = _ENTITY_SUFFIX_RE.sub("", path.stem)
        local_to_file[_normalize_for_lookup(stem)] = path.name
        meta = read_frontmatter(path)
        label_val = meta.get("label")
        if isinstance(label_val, str) and label_val.strip():
            local_to_file[_normalize_for_lookup(label_val.strip())] = path.name

    class_colors: dict[str, str] = {
        cls: _CLASS_COLORS[i % len(_CLASS_COLORS)]
        for i, cls in enumerate(pack_classes)
    }

    node_labels: dict[str, str] = {}  # iri → display label
    node_types: dict[str, str] = {}   # iri → class name
    edges: list[tuple[str, str, str]] = []  # (subj_iri, pred_local, obj_iri)

    for triple_str in triples:
        if not triple_str.lstrip().startswith("<"):
            continue
        iris = _IRI_IN_TRIPLE_RE.findall(triple_str)
        if len(iris) < 2:
            continue
        subj_iri, pred_iri = iris[0], iris[1]
        if pred_iri == _RDF_TYPE and len(iris) >= 3:
            node_types[subj_iri] = _local_name(iris[2])
        elif pred_iri == _RDFS_LABEL:
            m = _LITERAL_IN_TRIPLE_RE.search(triple_str)
            if m:
                node_labels[subj_iri] = m.group(1)
        elif len(iris) >= 3 and not _LITERAL_IN_TRIPLE_RE.search(triple_str):
            edges.append((subj_iri, _local_name(pred_iri), iris[2]))

    all_iris = (
        set(node_labels)
        | set(node_types)
        | {s for s, _, _ in edges}
        | {o for _, _, o in edges}
    )

    def _node_id(iri: str) -> str:
        local = _local_name(iri)
        filename = local_to_file.get(_normalize_for_lookup(local), f"{local}.md")
        return _url_quote(filename, safe="")

    lines = [
        "digraph vault {",
        "  rankdir=LR;",
        '  node [shape=box style=filled fontsize=11 fontname="Helvetica"];',
    ]
    for iri in sorted(all_iris):
        label = node_labels.get(iri, _local_name(iri))
        cls = node_types.get(iri, "")
        color = class_colors.get(cls, "#e9ecef")
        nid = _node_id(iri)
        safe_label = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(
            f'  "{nid}" [label="{safe_label}" fillcolor="{color}" tooltip="{nid}"];'
        )
    for subj, pred_local, obj in edges:
        sid = _node_id(subj)
        oid = _node_id(obj)
        safe_pred = pred_local.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  "{sid}" -> "{oid}" [label="{safe_pred}"];')
    lines.append("}")
    return "\n".join(lines)
