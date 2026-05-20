"""Write extracted entities to a vault as Markdown+YAML files.

Lifted from scripts/extractor.py:entity_to_markdown / write_vault_files.
URI base, prefix, and per-entity PDF-link path come from the DomainPack.
"""
from __future__ import annotations

import re
from pathlib import Path
from textwrap import dedent

import yaml

from callimachus.pack import DomainPack

# Relative path (from a vault/*.md file) to the directory holding source PDFs.
# Matches the legacy extractor; safe to override per-project later.
PDF_LINK_BASE = "sources"


def entity_to_markdown(
    entity: dict,
    doc_id: str,
    prompt_version: str,
    model_snapshot: str,
    pack: DomainPack,
) -> str:
    eid = entity["id"]
    label = entity["label"]
    cls = entity["class"]
    source_section = entity.get("source_section", "")
    source_text = entity.get("source_text", "")
    source_page = entity.get("source_page")
    raw_properties = entity.get("properties") or {}

    # Wrap object-property values in Obsidian wikilink syntax so Properties
    # become graph edges; datatype properties (literals) pass through unwrapped.
    # to_turtle.py strips the brackets when emitting RDF. List values (the
    # LLM may legitimately return one or more codes per excerpt, etc.) are
    # mapped element-wise so the YAML stays a list of wikilinks rather than
    # one wikilink wrapping a Python list literal.
    datatype_props = {p.name for p in pack.properties if p.datatype}

    def _wrap(value):
        if isinstance(value, str) and value.startswith("[["):
            return value
        return f"[[{value}]]"

    properties = {}
    for k, v in raw_properties.items():
        # Strict empty check: keep 0 / False / "0" — only skip None or "".
        if v is None or v == "":
            continue
        if k in datatype_props:
            # Datatype properties: emit as-is. List literals are kept as
            # lists; the Turtle writer expands them into multiple triples.
            properties[k] = v
        elif isinstance(v, list):
            properties[k] = [_wrap(x) for x in v if x not in (None, "")]
        else:
            properties[k] = _wrap(v)

    meta = {
        "class":           cls,
        "id":              eid,
        "label":           label,
        "uri":             f"{pack.entity_iri}{eid}",
        "source_document": doc_id,
        "source_section":  source_section,
        "source_page":     source_page,
        "source_text":     source_text,
        "properties":      properties,
        "prompt_version":  prompt_version,
        "model_snapshot":  model_snapshot,
        "validation":      "PENDING",
    }
    if source_page is None:
        meta.pop("source_page")

    frontmatter = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)

    if source_page:
        # Per-entity PDF (one highlight per entity); see scripts/highlight.py.
        source_line = (
            f"**Source:** [{source_section} — page {source_page}]"
            f"({PDF_LINK_BASE}/{eid}.pdf#page={source_page})"
        )
    else:
        source_line = f"**Source:** {source_section} — {doc_id}"

    body = dedent(f"""\
        ## {label}

        **Class:** `{pack.prefix}:{cls}`
        {source_line}

        > {source_text}

        *Auto-extracted by extractor.py. Review before merging.*
    """)

    return f"---\n{frontmatter}---\n\n{body}"


def write_vault_files(
    entities: list[dict],
    vault_dir: Path,
    doc_id: str,
    prompt_version: str,
    model_snapshot: str,
    pack: DomainPack,
) -> list[Path]:
    vault_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for entity in entities:
        eid = entity.get("id")
        if not eid:
            continue
        # sanitise id to safe filename
        safe = re.sub(r"[^a-z0-9_]", "_", eid.lower())
        out_path = vault_dir / f"{safe}.md"
        content = entity_to_markdown(entity, doc_id, prompt_version, model_snapshot, pack)
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)
        print(f"[extractor] wrote {out_path.name}")
    return written
