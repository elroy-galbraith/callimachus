"""Apply approved consolidator proposals to the vault.

Reads proposal markdown files (status: approved), performs the
operation against the vault, and marks the proposal file as
`status: applied`. Idempotent: re-running won't re-apply a proposal
that's already been marked applied.

Operations implemented:
  - rename_label    — change the `label:` field on one entity file
  - link_hierarchy  — add a property -> wikilink on one entity file
  - merge_entities  — rewrite wikilinks across the vault, delete removed file
  - group_codes     — write a new Subtheme file, link it from parent Theme
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import yaml

from callimachus.engine.consolidator import (
    list_proposal_files,
    load_proposal_file,
    set_proposal_status,
)
from callimachus.pack import DomainPack

WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
FRONTMATTER_RE = re.compile(r"^(---\n)(.*?)(\n---)", re.DOTALL)


@dataclass
class ApplyResult:
    proposal_id: str
    operation: str
    ok: bool
    message: str
    touched: list[str]   # vault-relative paths of files changed


def apply_approved(vault_dir: Path, pack: DomainPack) -> list[ApplyResult]:
    """Apply every proposal with status == 'approved' and mark them 'applied'."""
    results: list[ApplyResult] = []
    for path in list_proposal_files(vault_dir):
        meta = load_proposal_file(path)
        if not meta or meta.get("status") != "approved":
            continue
        try:
            res = _apply_one(meta, vault_dir, pack)
        except Exception as exc:
            results.append(ApplyResult(
                proposal_id=meta.get("proposal_id", path.stem),
                operation=meta.get("operation", "?"),
                ok=False, message=f"error: {exc}", touched=[],
            ))
            continue
        results.append(res)
        if res.ok:
            set_proposal_status(path, "applied",
                                reviewer_notes=meta.get("reviewer_notes") or None)
    return results


def _apply_one(meta: dict, vault_dir: Path, pack: DomainPack) -> ApplyResult:
    op = meta.get("operation", "")
    pid = meta.get("proposal_id", "?")
    if op == "rename_label":
        return _apply_rename_label(meta, vault_dir, pid)
    if op == "link_hierarchy":
        return _apply_link_hierarchy(meta, vault_dir, pid)
    if op == "merge_entities":
        return _apply_merge_entities(meta, vault_dir, pid)
    if op == "group_codes":
        return _apply_group_codes(meta, vault_dir, pid, pack)
    return ApplyResult(pid, op, False, f"operation {op!r} not implemented", [])


# ── Per-operation implementations ────────────────────────────────────────────


def _entity_path(vault_dir: Path, entity_id: str) -> Path | None:
    """Locate the vault file for a given entity id."""
    safe = re.sub(r"[^a-z0-9_]", "_", entity_id.lower())
    candidate = vault_dir / f"{safe}.md"
    return candidate if candidate.exists() else None


def _update_frontmatter(path: Path, mutate) -> None:
    """Read frontmatter, pass it through `mutate(meta) -> meta`, write back."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"no frontmatter in {path}")
    meta = yaml.safe_load(m.group(2)) or {}
    meta = mutate(meta)
    new_yaml = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    new_text = f"{m.group(1)}{new_yaml.rstrip()}{m.group(3)}{text[m.end():]}"
    path.write_text(new_text, encoding="utf-8")


def _apply_rename_label(meta: dict, vault_dir: Path, pid: str) -> ApplyResult:
    eid = meta.get("entity_id")
    new_label = meta.get("new_label")
    if not eid or not new_label:
        return ApplyResult(pid, "rename_label", False,
                           "missing entity_id or new_label", [])
    path = _entity_path(vault_dir, eid)
    if not path:
        return ApplyResult(pid, "rename_label", False,
                           f"entity {eid!r} not found in vault", [])

    def mut(m: dict) -> dict:
        m["label"] = new_label
        return m
    _update_frontmatter(path, mut)
    return ApplyResult(pid, "rename_label", True,
                       f"relabelled {eid} -> {new_label!r}",
                       [path.name])


def _apply_link_hierarchy(meta: dict, vault_dir: Path, pid: str) -> ApplyResult:
    from_id = meta.get("from_id")
    to_id = meta.get("to_id")
    prop = meta.get("property")
    if not (from_id and to_id and prop):
        return ApplyResult(pid, "link_hierarchy", False,
                           "missing from_id, to_id, or property", [])
    src = _entity_path(vault_dir, from_id)
    if not src:
        return ApplyResult(pid, "link_hierarchy", False,
                           f"source entity {from_id!r} not found", [])

    target_link = f"[[{to_id}]]"

    def mut(m: dict) -> dict:
        props = m.get("properties") or {}
        existing = props.get(prop)
        if existing is None:
            props[prop] = target_link
        elif isinstance(existing, list):
            if target_link not in existing and to_id not in existing:
                existing.append(target_link)
        else:
            # scalar already set; promote to a list if different
            existing_id = existing[2:-2] if str(existing).startswith("[[") else existing
            if existing_id != to_id:
                props[prop] = [existing, target_link]
        m["properties"] = props
        return m
    _update_frontmatter(src, mut)
    return ApplyResult(pid, "link_hierarchy", True,
                       f"added {prop}: {target_link} on {from_id}",
                       [src.name])


def _apply_merge_entities(meta: dict, vault_dir: Path, pid: str) -> ApplyResult:
    kept = meta.get("kept_id")
    removed = meta.get("removed_id")
    if not (kept and removed):
        return ApplyResult(pid, "merge_entities", False,
                           "missing kept_id or removed_id", [])
    if kept == removed:
        return ApplyResult(pid, "merge_entities", False,
                           "kept_id == removed_id, refusing to no-op", [])

    kept_path = _entity_path(vault_dir, kept)
    removed_path = _entity_path(vault_dir, removed)
    if not kept_path:
        return ApplyResult(pid, "merge_entities", False,
                           f"kept entity {kept!r} not found", [])

    touched: list[str] = []
    # Rewrite every wikilink to the removed id across the vault, in both
    # frontmatter property values and body text.
    for path in sorted(vault_dir.glob("*.md")):
        if removed_path is not None and path == removed_path:
            continue
        text = path.read_text(encoding="utf-8")
        new_text = WIKILINK_RE.sub(
            lambda m: f"[[{kept}]]" if m.group(1).strip() == removed else m.group(0),
            text,
        )
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            touched.append(path.name)

    if removed_path is not None and removed_path.exists():
        removed_path.unlink()
        touched.append(f"{removed_path.name} (deleted)")
    return ApplyResult(pid, "merge_entities", True,
                       f"merged {removed} -> {kept}", touched)


def _apply_group_codes(meta: dict, vault_dir: Path, pid: str,
                       pack: DomainPack) -> ApplyResult:
    new_label = meta.get("new_subtheme_label")
    parent = meta.get("parent_theme_id")
    members = meta.get("member_code_ids") or []
    if not (new_label and parent):
        return ApplyResult(pid, "group_codes", False,
                           "missing new_subtheme_label or parent_theme_id", [])
    parent_path = _entity_path(vault_dir, parent)
    if not parent_path:
        return ApplyResult(pid, "group_codes", False,
                           f"parent theme {parent!r} not found", [])

    # Derive a new Subtheme id, namespaced under the parent's document.
    parent_meta = yaml.safe_load(
        FRONTMATTER_RE.match(parent_path.read_text(encoding="utf-8")).group(2)
    ) or {}
    doc_id = parent_meta.get("source_document") or "doc"
    slug = re.sub(r"[^a-z0-9_]", "_", new_label.lower()).strip("_")[:50] or "subtheme"
    new_id = f"{doc_id}_subtheme_{slug}"

    new_path = vault_dir / f"{new_id}.md"
    if new_path.exists():
        return ApplyResult(pid, "group_codes", False,
                           f"target Subtheme file already exists: {new_path.name}", [])

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    members_list = "\n".join(f"- [[{m}]]" for m in members)
    sub_meta = {
        "class":           "Subtheme",
        "id":              new_id,
        "label":           new_label,
        "uri":             f"{pack.entity_iri}{new_id}",
        "source_document": doc_id,
        "source_section":  "consolidator",
        "source_text":     f"Subtheme proposed by the consolidator, grouping "
                           f"{len(members)} Codes.",
        "properties":      {},
        "prompt_version":  "consolidator-v1",
        "model_snapshot":  meta.get("model_snapshot", pack.models.ask),
        "validation":      "PENDING",
        "created_at":      now,
        "member_codes":    [f"[[{m}]]" for m in members],  # informational
    }
    frontmatter = yaml.dump(sub_meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    body = dedent(f"""\
        ## {new_label}

        **Class:** `{pack.prefix}:Subtheme`
        **Parent Theme:** [[{parent}]]

        Member codes (per consolidator proposal `{pid}`):

        {members_list}
        """)
    new_path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    touched = [new_path.name]

    # Add `hasSubtheme: [[new_id]]` on the parent Theme.
    def mut(m: dict) -> dict:
        props = m.get("properties") or {}
        link = f"[[{new_id}]]"
        existing = props.get("hasSubtheme")
        if existing is None:
            props["hasSubtheme"] = link
        elif isinstance(existing, list):
            if link not in existing:
                existing.append(link)
        else:
            if existing != link:
                props["hasSubtheme"] = [existing, link]
        m["properties"] = props
        return m
    _update_frontmatter(parent_path, mut)
    touched.append(parent_path.name)

    return ApplyResult(pid, "group_codes", True,
                       f"created Subtheme {new_id!r} under {parent}", touched)
