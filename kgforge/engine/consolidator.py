"""LLM-driven consolidator: propose vault-level edits that a deterministic
linter can't make on its own (merging near-duplicate Codes/Themes, grouping
Codes under a missing Subtheme, suggesting label rewrites for consistency).

Read-only by design — produces a list of typed Proposals as data, never
mutates the vault. A separate apply step (or a human review UI) is what
turns Proposals into commits.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import anthropic
import yaml

from kgforge.pack import DomainPack

CONSOLIDATOR_MAX_TOKENS = 4096


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
        for raw in block.input.get("proposals", []):
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
