"""LLM-driven consolidator: propose vault-level edits that a deterministic
linter can't make on its own (merging near-duplicate Codes/Themes, grouping
Codes under a missing Subtheme, suggesting label rewrites for consistency).

Read-only by design — produces a list of typed Proposals as data, never
mutates the vault. A separate apply step (or a human review UI) is what
turns Proposals into commits.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

import anthropic
import yaml

from kgforge.pack import DomainPack

# Output budget for the propose_consolidation tool call. Vaults with many
# entities can warrant 50+ proposals; each is ~150-300 output tokens so
# 16K is a safe headroom (still well under Sonnet 4.6's 64K cap).
CONSOLIDATOR_MAX_TOKENS = 16384

# Subdirectory inside the vault where proposal markdown files live.
PROPOSALS_DIRNAME = "proposals"


@dataclass
class Proposal:
    operation: str           # "merge_entities" | "group_codes" | "link_hierarchy" | "rename_label"
    rationale: str
    confidence: str          # "high" | "medium" | "low"
    evidence: list[str]      # quoted excerpt source_texts that justify the move
    payload: dict[str, Any]  # operation-specific fields (see schema below)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Vault loading ─────────────────────────────────────────────────────────────


def _parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def _load_vault(vault_dir: Path) -> list[dict]:
    """Return a compact dict per entity, suitable for stuffing into a prompt."""
    out: list[dict] = []
    for path in sorted(vault_dir.glob("*.md")):
        meta = _parse_frontmatter(path)
        if not meta or not meta.get("id"):
            continue
        out.append({
            "id": meta["id"],
            "class": meta.get("class", ""),
            "label": meta.get("label", ""),
            "source_section": meta.get("source_section", ""),
            "source_text": (meta.get("source_text") or "").strip(),
            "properties": meta.get("properties") or {},
        })
    return out


# ── Tool schema ───────────────────────────────────────────────────────────────


def _proposal_schema() -> dict:
    """JSON Schema for the propose_consolidation tool input."""
    return {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": [
                                "merge_entities",
                                "group_codes",
                                "link_hierarchy",
                                "rename_label",
                            ],
                        },
                        "rationale": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Verbatim source_text snippets from the vault that justify this proposal.",
                        },
                        # merge_entities payload
                        "kept_id":    {"type": "string"},
                        "removed_id": {"type": "string"},
                        # group_codes payload
                        "new_subtheme_label": {"type": "string"},
                        "parent_theme_id":    {"type": "string"},
                        "member_code_ids":    {"type": "array", "items": {"type": "string"}},
                        # link_hierarchy payload
                        "from_id":  {"type": "string"},
                        "property": {"type": "string"},
                        "to_id":    {"type": "string"},
                        # rename_label payload
                        "entity_id": {"type": "string"},
                        "new_label": {"type": "string"},
                    },
                    "required": ["operation", "rationale", "confidence", "evidence"],
                },
            }
        },
        "required": ["proposals"],
    }


# ── Prompt ────────────────────────────────────────────────────────────────────


_SYSTEM = """You are a qualitative-research methodologist reviewing a knowledge
graph extracted from interview transcripts. Your job is to PROPOSE
consolidations that a human reviewer will approve or reject - you do not
mutate anything yourself.

The graph follows this schema:
{classes_block}

With these properties (domain -> range):
{properties_block}

Look across the full vault and propose operations of these kinds:

1. merge_entities - two entities of the SAME CLASS whose labels describe the
   same construct (e.g. "Lack of transparency" and "Feeling shut out" as
   Codes). Set kept_id to the entity whose label/id you'd preserve.

2. group_codes - several Codes that recur and should be lifted into a new
   Subtheme that doesn't yet exist. Provide new_subtheme_label and the
   parent_theme_id it should attach to. Only propose if 2+ Codes cohere.

3. link_hierarchy - a structural gap where two existing entities should be
   linked via a declared property (e.g. a Theme that lacks hasSubtheme to a
   Subtheme that clearly belongs under it).

4. rename_label - an entity whose label is awkward, redundant, or
   inconsistent with sibling labels. Provide new_label.

Rules:
  - Be conservative. If two Codes describe SUBTLY different constructs, do
    NOT propose a merge - propose group_codes under a shared Subtheme instead.
  - Every proposal MUST include at least one verbatim source_text snippet
    from the vault in evidence[] that demonstrates the construct.
  - Use "low" confidence freely; reviewers will filter.
  - It is fine to return an empty proposals list if the vault is clean.
"""

_USER_TEMPLATE = """Below is the full vault as JSON. Propose consolidations.

VAULT:
{vault_json}

Use the propose_consolidation tool.
"""


def _render_system(pack: DomainPack) -> str:
    return _SYSTEM.format(
        classes_block=pack.render_classes_block(),
        properties_block=pack.render_properties_block(),
    )


# ── Public API ────────────────────────────────────────────────────────────────


def consolidate(
    vault_dir: Path,
    pack: DomainPack,
    *,
    model: str | None = None,
) -> list[Proposal]:
    """Read the vault, call the LLM, return a list of typed proposals."""
    entities = _load_vault(vault_dir)
    if not entities:
        return []

    client = anthropic.Anthropic()
    system = _render_system(pack)
    user = _USER_TEMPLATE.format(vault_json=json.dumps(entities, indent=2))

    response = client.messages.create(
        model=model or pack.models.ask,
        max_tokens=CONSOLIDATOR_MAX_TOKENS,
        system=system,
        tools=[
            {
                "name": "propose_consolidation",
                "description": "Submit a list of proposed consolidations for human review.",
                "input_schema": _proposal_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "propose_consolidation"},
        messages=[{"role": "user", "content": user}],
    )

    proposals: list[Proposal] = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        raw_proposals = block.input.get("proposals", [])
        if not raw_proposals and response.stop_reason == "max_tokens":
            import sys
            print(
                f"[consolidator] WARNING: tool call truncated at "
                f"max_tokens={CONSOLIDATOR_MAX_TOKENS} "
                f"(stop_reason=max_tokens, output_tokens="
                f"{response.usage.output_tokens}). Raise "
                f"CONSOLIDATOR_MAX_TOKENS or split the vault.",
                file=sys.stderr,
            )
        for raw in raw_proposals:
            proposals.append(_to_proposal(raw))
    return proposals


def _to_proposal(raw: dict) -> Proposal:
    op = raw["operation"]
    # Carve out the payload fields per operation, leaving the four
    # always-required fields off the payload dict.
    payload_keys = {
        "merge_entities":  ("kept_id", "removed_id"),
        "group_codes":     ("new_subtheme_label", "parent_theme_id", "member_code_ids"),
        "link_hierarchy":  ("from_id", "property", "to_id"),
        "rename_label":    ("entity_id", "new_label"),
    }.get(op, ())
    payload = {k: raw.get(k) for k in payload_keys if k in raw}
    return Proposal(
        operation=op,
        rationale=raw.get("rationale", ""),
        confidence=raw.get("confidence", "medium"),
        evidence=raw.get("evidence", []),
        payload=payload,
    )


# ── Markdown proposal files ───────────────────────────────────────────────────


def proposal_fingerprint(p: Proposal) -> str:
    """Stable 8-char hash over the operation + key payload fields.

    Re-running the consolidator with similar output then yields the same
    filename, so an existing user decision (`status: approved`) is
    preserved instead of being shadowed by a fresh `status: pending` file.
    """
    op = p.operation
    if op == "merge_entities":
        key = (p.payload.get("kept_id"), p.payload.get("removed_id"))
    elif op == "group_codes":
        members = tuple(sorted(p.payload.get("member_code_ids") or []))
        key = (p.payload.get("parent_theme_id"), members)
    elif op == "link_hierarchy":
        key = (p.payload.get("from_id"), p.payload.get("property"), p.payload.get("to_id"))
    elif op == "rename_label":
        key = (p.payload.get("entity_id"),)
    else:
        key = (json.dumps(p.payload, sort_keys=True),)
    digest = hashlib.sha1(f"{op}|{key}".encode("utf-8")).hexdigest()
    return digest[:8]


def _proposal_slug(p: Proposal) -> str:
    """Short human-readable slug for the filename."""
    if p.operation == "merge_entities":
        return f"merge_{p.payload.get('kept_id', 'x')}"
    if p.operation == "group_codes":
        return f"group_{_slugify(p.payload.get('new_subtheme_label', 'codes'))}"
    if p.operation == "link_hierarchy":
        return f"link_{p.payload.get('from_id', 'x')}"
    if p.operation == "rename_label":
        return f"rename_{p.payload.get('entity_id', 'x')}"
    return p.operation


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", (s or "").lower())[:40].strip("_") or "x"


def _wiki(entity_id: str | None) -> str:
    return f"[[{entity_id}]]" if entity_id else "—"


def _render_body(p: Proposal) -> str:
    op = p.operation
    pl = p.payload
    if op == "merge_entities":
        return dedent(f"""\
            ## Merge two entities

            **Keep:** {_wiki(pl.get('kept_id'))}
            **Remove:** {_wiki(pl.get('removed_id'))}

            Applying this proposal will rewrite every wikilink pointing to
            `{pl.get('removed_id')}` so it points to `{pl.get('kept_id')}`,
            then delete the file `{pl.get('removed_id')}.md`.
            """)
    if op == "group_codes":
        members = pl.get("member_code_ids") or []
        member_list = "\n".join(f"- {_wiki(m)}" for m in members)
        return dedent(f"""\
            ## Group codes under a new Subtheme

            **New Subtheme:** `{pl.get('new_subtheme_label')}`
            **Under Theme:** {_wiki(pl.get('parent_theme_id'))}

            **Member codes:**
            {member_list}

            Applying this proposal will create a new Subtheme markdown file
            and add `hasSubtheme: [[new-subtheme]]` to the parent Theme.
            """)
    if op == "link_hierarchy":
        return dedent(f"""\
            ## Add a hierarchy link

            Add property `{pl.get('property')}` on {_wiki(pl.get('from_id'))}
            pointing to {_wiki(pl.get('to_id'))}.
            """)
    if op == "rename_label":
        return dedent(f"""\
            ## Rename an entity's label

            **Entity:** {_wiki(pl.get('entity_id'))}
            **New label:** `{pl.get('new_label')}`
            """)
    return f"## {op}\n\nUnknown operation type."


def write_proposal_files(
    proposals: list[Proposal],
    vault_dir: Path,
    *,
    model_snapshot: str,
) -> list[Path]:
    """Write each proposal to <vault>/proposals/<id>.md.

    If a file with the same fingerprint already exists, its `status:` and
    any reviewer-added notes are preserved; only the LLM-generated fields
    (rationale, evidence, confidence) are refreshed. That way a re-run
    doesn't clobber existing decisions.
    """
    out_dir = vault_dir / PROPOSALS_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for idx, p in enumerate(proposals, 1):
        fp = proposal_fingerprint(p)
        slug = _proposal_slug(p)
        filename = f"proposal_{fp}_{slug}.md"
        path = out_dir / filename

        existing_status = "pending"
        existing_notes = ""
        if path.exists():
            try:
                existing = _parse_frontmatter(path) or {}
                existing_status = existing.get("status", "pending")
                existing_notes = existing.get("reviewer_notes", "") or ""
            except Exception:
                pass

        meta: dict[str, Any] = {
            "proposal_id":    f"proposal_{fp}",
            "operation":      p.operation,
            "status":         existing_status,
            "confidence":     p.confidence,
            "created_at":     now,
            "model_snapshot": model_snapshot,
        }
        # Operation-specific payload fields flatten into top-level frontmatter
        # so the UI can read them without recursing into a nested dict.
        for k, v in p.payload.items():
            if v is None:
                continue
            meta[k] = v
        meta["rationale"] = p.rationale
        meta["evidence"]  = p.evidence
        if existing_notes:
            meta["reviewer_notes"] = existing_notes

        frontmatter = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
        body = _render_body(p)
        path.write_text(f"---\n{frontmatter}---\n\n{body}\n", encoding="utf-8")
        written.append(path)

    return written


def list_proposal_files(vault_dir: Path) -> list[Path]:
    """Return all proposal markdown files for the vault."""
    out_dir = vault_dir / PROPOSALS_DIRNAME
    if not out_dir.exists():
        return []
    return sorted(out_dir.glob("proposal_*.md"))


def load_proposal_file(path: Path) -> dict | None:
    return _parse_frontmatter(path)


def set_proposal_status(path: Path, status: str, *, reviewer_notes: str | None = None) -> None:
    """Update the `status` (and optionally `reviewer_notes`) on a proposal file.

    Preserves the body and all other frontmatter fields.
    """
    if status not in {"pending", "approved", "rejected", "deferred", "applied"}:
        raise ValueError(f"unknown proposal status: {status!r}")
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"no frontmatter in {path}")
    meta = yaml.safe_load(m.group(1)) or {}
    meta["status"] = status
    if reviewer_notes is not None:
        meta["reviewer_notes"] = reviewer_notes
    body = m.group(2)
    frontmatter = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
