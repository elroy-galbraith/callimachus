"""Read-side helpers for surfacing consolidator proposals over HTTP.

``proposal_dot`` mirrors the Streamlit ``_graph_for`` function verbatim
so the React app gets the same mini-graphs. ``payload_summary`` mirrors
``_render_payload_summary``. ``find_proposal_file`` resolves a
``proposal_id`` (e.g. ``"proposal_abcd1234"``) to its path on disk.

Lives in the API layer rather than the engine because both functions are
presentation-shaped (DOT strings, English prose) and the engine treats
proposals as pure data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from kgforge.engine.consolidator import (
    PROPOSALS_DIRNAME,
    list_proposal_files,
    load_proposal_file,
)


VALID_STATUSES = {"pending", "approved", "rejected", "deferred", "applied"}


# ---------- DOT mini-graphs ------------------------------------------------


def proposal_dot(meta: dict[str, Any]) -> str | None:
    """Return a DOT-string mini-graph for a proposal, or None.

    Convention: green dashed = added; red dashed with strikethrough label
    = removed; black = unchanged context. Identical output to the
    Streamlit ``_graph_for`` so the React render is a pixel-for-pixel
    parity check.
    """
    op = meta.get("operation")
    if op == "merge_entities":
        kept = meta.get("kept_id", "kept")
        removed = meta.get("removed_id", "removed")
        return (
            "digraph G {\n"
            '  rankdir=LR; node [shape=box, style=rounded];\n'
            f'  "{kept}" [color="darkgreen", penwidth=2, label="{kept}\\n(keep)"];\n'
            f'  "{removed}" [color="firebrick", style="dashed,rounded", '
            f'label=<<S>{removed}</S><BR/>(remove)>];\n'
            f'  "{removed}" -> "{kept}" [label="merge into", color="darkgreen", '
            f'style="dashed"];\n'
            "}\n"
        )
    if op == "group_codes":
        parent = meta.get("parent_theme_id", "parent_theme")
        new_label = meta.get("new_subtheme_label", "new subtheme")
        members = meta.get("member_code_ids") or []
        lines = [
            "digraph G {\n",
            "  node [shape=box, style=rounded];\n",
            f'  "{parent}" [label="Theme:\\n{parent}"];\n',
            f'  "NEW" [color="darkgreen", style="dashed,rounded", penwidth=2, '
            f'label="(new Subtheme)\\n{new_label}"];\n',
            f'  "{parent}" -> "NEW" [color="darkgreen", style="dashed", '
            f'label="hasSubtheme"];\n',
        ]
        for m in members:
            lines.append(f'  "{m}" [shape=box, style=rounded];\n')
            lines.append(
                f'  "NEW" -> "{m}" [color="darkgreen", style="dashed", '
                f'label="(implied)"];\n'
            )
        lines.append("}\n")
        return "".join(lines)
    if op == "link_hierarchy":
        f = meta.get("from_id", "from")
        t = meta.get("to_id", "to")
        prop = meta.get("property", "rel")
        return (
            "digraph G {\n"
            '  rankdir=LR; node [shape=box, style=rounded];\n'
            f'  "{f}"; "{t}";\n'
            f'  "{f}" -> "{t}" [color="darkgreen", style="dashed", '
            f'label="{prop} (new)"];\n'
            "}\n"
        )
    if op == "rename_label":
        eid = meta.get("entity_id", "entity")
        new_label = meta.get("new_label", "?")
        return (
            "digraph G {\n"
            "  node [shape=box, style=rounded];\n"
            f'  "{eid}" [label=<{eid}<BR/><FONT POINT-SIZE="10" COLOR="darkgreen">'
            f"label → {new_label}</FONT>>];\n"
            "}\n"
        )
    return None


# ---------- English payload summaries --------------------------------------


def payload_summary(meta: dict[str, Any]) -> str:
    op = meta.get("operation")
    if op == "merge_entities":
        return (
            f"Keep `{meta.get('kept_id')}`, remove `{meta.get('removed_id')}`."
        )
    if op == "group_codes":
        members = meta.get("member_code_ids") or []
        return (
            f"New Subtheme '{meta.get('new_subtheme_label')}' under "
            f"`{meta.get('parent_theme_id')}` ({len(members)} member code(s))."
        )
    if op == "link_hierarchy":
        return (
            f"`{meta.get('from_id')}` —{meta.get('property')}→ "
            f"`{meta.get('to_id')}`."
        )
    if op == "rename_label":
        return (
            f"`{meta.get('entity_id')}` → label '{meta.get('new_label')}'."
        )
    return str(op or "?")


# ---------- File lookup ----------------------------------------------------


def find_proposal_file(vault_dir: Path, proposal_id: str) -> Path | None:
    """Resolve ``proposal_id`` (e.g. ``proposal_abcd1234``) to its file.

    Proposal filenames are ``proposal_<fp>_<slug>.md`` and the frontmatter
    ``proposal_id`` is ``proposal_<fp>``. We scan the proposals dir and
    match on the frontmatter rather than filename prefixes, so a slug
    change between consolidator runs doesn't break links.
    """
    out_dir = vault_dir / PROPOSALS_DIRNAME
    if not out_dir.exists():
        return None
    for path in list_proposal_files(vault_dir):
        meta = load_proposal_file(path) or {}
        if meta.get("proposal_id") == proposal_id:
            return path
    return None
