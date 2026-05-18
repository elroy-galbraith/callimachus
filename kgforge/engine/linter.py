"""Deterministic linter for vault markdown produced by the extractor.

Catches mechanical and structural problems that don't need an LLM:
required frontmatter, unknown class/property names, wikilinks that point
nowhere, domain violations (e.g. an Excerpt property used on a Subtheme),
orphan entities, hierarchy gaps. Returns a list of Finding objects; the
CLI in scripts/lint.py renders them.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from kgforge.pack import DomainPack

REQUIRED_FIELDS = ("class", "id", "label", "uri", "source_document")
EXCERPT_REQUIRED_PROPS = ("spokenBy",)
WIKILINK_RE = re.compile(r"^\[\[(.+?)\]\]$")


@dataclass
class Finding:
    severity: str          # "error" | "warn" | "info"
    rule: str              # short slug, e.g. "domain_violation"
    entity_id: str         # may be "" if frontmatter couldn't be parsed
    file: str              # vault-relative path
    message: str
    suggested_fix: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _strip_wikilink(value) -> str:
    m = WIKILINK_RE.match(str(value).strip())
    return m.group(1) if m else str(value).strip()


def _iter_wikilink_targets(value):
    """Yield each wikilink target in a property value (scalar or list)."""
    items = value if isinstance(value, list) else [value]
    for v in items:
        if v is None or v == "":
            continue
        yield _strip_wikilink(v)


def _parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def lint_vault(vault_dir: Path, pack: DomainPack) -> list[Finding]:
    """Walk vault/*.md and produce findings against the pack's schema."""
    findings: list[Finding] = []
    md_files = sorted(vault_dir.glob("*.md"))

    # Pass 1: parse every entity. Build lookup tables for cross-entity checks.
    entities: dict[str, dict] = {}   # id -> frontmatter
    entity_file: dict[str, Path] = {}
    for path in md_files:
        rel = path.name
        meta = _parse_frontmatter(path)
        if meta is None:
            findings.append(Finding(
                "error", "no_frontmatter", "", rel,
                "file has no YAML frontmatter; extractor output is malformed",
            ))
            continue
        eid = meta.get("id") or ""
        if not eid:
            findings.append(Finding(
                "error", "missing_id", "", rel,
                "frontmatter has no `id:` field",
            ))
            continue
        if eid in entities:
            findings.append(Finding(
                "error", "duplicate_id", eid, rel,
                f"id {eid!r} already declared in {entity_file[eid].name}",
            ))
            continue
        entities[eid] = meta
        entity_file[eid] = path

    # Build pack-derived lookups.
    class_names = set(pack.class_names)
    property_by_name = {p.name: p for p in pack.properties}
    datatype_props = {p.name for p in pack.properties if p.datatype}

    # Pass 2: per-entity checks.
    for eid, meta in entities.items():
        path = entity_file[eid]
        rel = path.name
        cls = meta.get("class", "")

        for field in REQUIRED_FIELDS:
            if not meta.get(field):
                findings.append(Finding(
                    "error", "missing_required_field", eid, rel,
                    f"required frontmatter field missing or empty: {field!r}",
                ))

        if cls and cls not in class_names:
            findings.append(Finding(
                "error", "unknown_class", eid, rel,
                f"class {cls!r} is not declared in pack {pack.metadata.name!r}; "
                f"valid: {sorted(class_names)}",
            ))

        # id ↔ filename consistency (filenames are sanitised lowercase).
        expected_stem = re.sub(r"[^a-z0-9_]", "_", eid.lower())
        if path.stem != expected_stem:
            findings.append(Finding(
                "warn", "filename_mismatch", eid, rel,
                f"filename {path.stem!r} doesn't match sanitised id {expected_stem!r}",
            ))

        # uri should end with the id (extractor builds it as <entity_iri>+id).
        uri = meta.get("uri", "")
        if uri and not uri.endswith(eid):
            findings.append(Finding(
                "warn", "uri_id_mismatch", eid, rel,
                f"uri {uri!r} doesn't end with id {eid!r}",
            ))

        # Excerpts need spokenBy + source_section.
        if cls == "Excerpt":
            props = meta.get("properties") or {}
            for required in EXCERPT_REQUIRED_PROPS:
                if not props.get(required):
                    findings.append(Finding(
                        "warn", "excerpt_missing_property", eid, rel,
                        f"Excerpt is missing required property {required!r}",
                    ))
            if not meta.get("source_section"):
                findings.append(Finding(
                    "warn", "excerpt_missing_source_section", eid, rel,
                    "Excerpt has no source_section (needed to cite the turn)",
                ))

        # Property-level checks.
        for prop_name, value in (meta.get("properties") or {}).items():
            prop_def = property_by_name.get(prop_name)
            if prop_def is None:
                findings.append(Finding(
                    "error", "unknown_property", eid, rel,
                    f"property {prop_name!r} is not declared in pack",
                ))
                continue
            if prop_def.domain and cls and cls != prop_def.domain:
                # Allow subclasses: a Subtheme is-a Theme via pack `parent:`.
                if not _class_is_subclass(cls, prop_def.domain, pack):
                    findings.append(Finding(
                        "error", "domain_violation", eid, rel,
                        f"property {prop_name!r} is only valid on class "
                        f"{prop_def.domain!r}, not {cls!r}",
                        suggested_fix=f"move this triple onto a {prop_def.domain} entity, "
                                      f"or invert the direction if the inverse property exists",
                    ))
            # Wikilink target resolution (object properties only).
            if prop_name not in datatype_props:
                for target in _iter_wikilink_targets(value):
                    if target not in entities:
                        findings.append(Finding(
                            "warn", "dangling_wikilink", eid, rel,
                            f"property {prop_name!r} → [[{target}]] doesn't resolve "
                            f"(no vault file with that id)",
                        ))
                    elif target == eid:
                        findings.append(Finding(
                            "warn", "self_reference", eid, rel,
                            f"property {prop_name!r} points to its own entity",
                        ))

    # Pass 3: graph-shape checks (orphans, hierarchy gaps).
    # Build inbound-edge index: target_id -> [(source_id, prop_name)].
    inbound: dict[str, list[tuple[str, str]]] = {}
    for eid, meta in entities.items():
        for prop_name, value in (meta.get("properties") or {}).items():
            if prop_name in datatype_props:
                continue
            for target in _iter_wikilink_targets(value):
                inbound.setdefault(target, []).append((eid, prop_name))

    for eid, meta in entities.items():
        cls = meta.get("class", "")
        if cls == "Code":
            referenced_by_excerpt = any(
                entities.get(src, {}).get("class") == "Excerpt"
                for src, _ in inbound.get(eid, [])
            )
            if not referenced_by_excerpt:
                findings.append(Finding(
                    "warn", "orphan_code", eid, entity_file[eid].name,
                    "Code is not referenced by any Excerpt's `codedAs`; "
                    "either remove it or code an excerpt with it",
                ))
        if cls == "Subtheme":
            referenced_by_theme = any(
                entities.get(src, {}).get("class") == "Theme" and prop == "hasSubtheme"
                for src, prop in inbound.get(eid, [])
            )
            if not referenced_by_theme:
                findings.append(Finding(
                    "warn", "orphan_subtheme", eid, entity_file[eid].name,
                    "Subtheme is not linked from any Theme via `hasSubtheme`; "
                    "hierarchy is disconnected",
                    suggested_fix="add `hasSubtheme: [[" + eid + "]]` to the parent Theme",
                ))
        if cls == "Theme":
            has_subtheme = bool((meta.get("properties") or {}).get("hasSubtheme"))
            if not has_subtheme:
                findings.append(Finding(
                    "info", "theme_without_subthemes", eid, entity_file[eid].name,
                    "Theme has no `hasSubtheme` - may be intentional, but the "
                    "hierarchy is flat",
                ))

    # Sort: errors first, then warns, then infos; stable on (rule, file).
    rank = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: (rank.get(f.severity, 3), f.rule, f.file))
    return findings


def _class_is_subclass(child: str, parent: str, pack: DomainPack) -> bool:
    """True iff `child` inherits from `parent` via the pack's class hierarchy."""
    if child == parent:
        return True
    classes = {c.name: c for c in pack.classes}
    cur = classes.get(child)
    while cur and cur.parent:
        if cur.parent == parent:
            return True
        cur = classes.get(cur.parent)
    return False


def summarise(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity for a one-line summary."""
    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts
