"""Convert vault Markdown+YAML files to Turtle RDF.

Lifted from scripts/to_turtle.py. Pack drives prefixes, namespace IRIs,
property → predicate map, and the class enum check.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from callimachus.pack import DomainPack


def _ttl_str(value: str) -> str:
    """Escape a string for Turtle triple-quoted literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_frontmatter(path: Path) -> dict | None:
    """Return YAML frontmatter dict from a Markdown file, or None."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    return yaml.safe_load(m.group(1))


def _strip_wikilink(value) -> str:
    """Strip Obsidian wikilink brackets if present: '[[id]]' -> 'id'."""
    m = re.match(r"^\[\[(.+?)\]\]$", str(value).strip())
    return m.group(1) if m else str(value).strip()


def _build_prefixes(pack: DomainPack) -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix owl:  <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix dcterms: <http://purl.org/dc/terms/> .\n"
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
        f"@prefix {pack.prefix}:  <{pack.base_iri}> .\n"
        f"@prefix {pack.entity_prefix}: <{pack.entity_iri}> .\n"
    )


def entity_to_triples(
    meta: dict,
    pack: DomainPack,
    *,
    datatype_props: set[str] | None = None,
    property_map: dict[str, str] | None = None,
) -> list[str]:
    """Emit Turtle triples for one entity.

    The optional `datatype_props` and `property_map` kwargs let `build_turtle`
    compute them once and pass them down to each entity, avoiding O(N×P)
    recomputation across a large vault. Both default to recomputing from the
    pack if absent, so existing callers keep working unchanged.
    """
    eid = meta.get("id", "")
    if not eid:
        return []

    if datatype_props is None:
        datatype_props = {p.name for p in pack.properties if p.datatype}
    if property_map is None:
        property_map = pack.property_map()

    cls = meta.get("class", "")
    label = meta.get("label", eid)
    source_text = meta.get("source_text", "")
    source_section = meta.get("source_section", "")
    properties = meta.get("properties", {}) or {}

    subject = f"{pack.entity_prefix}:{eid}"
    lines: list[str] = [f"{subject}"]

    # rdf:type — known classes get the pack's prefix; unknown defaults to the
    # pack's first class so renamed/typo'd entries degrade gracefully. The
    # pack model enforces min_length=1 on classes, so the first elif is the
    # normal fallback path; the final else is belt-and-braces in case a
    # partially-initialised model bypasses validation.
    if cls in pack.class_names:
        lines.append(f"    a {pack.prefix}:{cls} ;")
    elif pack.class_names:
        fallback = pack.class_names[0]
        lines.append(f'    a {pack.prefix}:{fallback} ;  # unknown class "{cls}" — defaulted')
    else:
        lines.append(f'    a owl:Thing ;  # unknown class "{cls}" and pack has no classes')

    # rdfs:label
    lines.append(f'    rdfs:label "{_ttl_str(label)}"@en ;')

    # skos:definition from source_text
    if source_text:
        clean = source_text.strip().replace("\n", " ")
        lines.append(f'    skos:definition """{_ttl_str(clean)}"""@en ;')

    # dcterms:source — section reference
    if source_section:
        lines.append(f'    dcterms:source "{_ttl_str(source_section)}" ;')

    # ontology properties (entries with explicit `iri:` in the pack — e.g.
    # partOfStatute → dcterms:isPartOf — are honoured here). Datatype
    # properties emit quoted literals; object properties emit
    # entity-prefixed IRIs. Both branches accept either a single value or a
    # list, emitting one triple per element so multi-valued properties (an
    # Excerpt with several codedAs Codes, a Theme with several Sub-themes)
    # round-trip correctly.
    for prop_key, prop_iri in property_map.items():
        value = properties.get(prop_key)
        if value is None or value == "":
            continue
        is_datatype = prop_key in datatype_props
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None or item == "":
                continue
            target = _strip_wikilink(item)
            if is_datatype:
                lines.append(f'    {prop_iri} "{_ttl_str(str(target))}" ;')
            else:
                if target == eid:
                    continue  # skip self-references on object properties
                lines.append(f"    {prop_iri} {pack.entity_prefix}:{target} ;")

    # close the triple set
    last = lines[-1]
    lines[-1] = last.rstrip(" ;") + " ."
    lines.append("")

    return lines


def build_turtle(vault_dir: Path, pack: DomainPack) -> str:
    # Compute pack-wide derived data once instead of per-entity.
    datatype_props = {p.name for p in pack.properties if p.datatype}
    property_map = pack.property_map()

    parts: list[str] = [_build_prefixes(pack), ""]
    md_files = sorted(vault_dir.glob("*.md"))
    if not md_files:
        print(f"[to_turtle] WARNING: no .md files found in {vault_dir}", file=sys.stderr)
    for path in md_files:
        meta = _parse_frontmatter(path)
        if meta is None:
            print(f"[to_turtle] SKIP {path.name}: no YAML frontmatter", file=sys.stderr)
            continue
        triples = entity_to_triples(
            meta, pack, datatype_props=datatype_props, property_map=property_map
        )
        if triples:
            parts.extend(triples)
        else:
            print(f"[to_turtle] SKIP {path.name}: missing 'id' field", file=sys.stderr)
    return "\n".join(parts)
