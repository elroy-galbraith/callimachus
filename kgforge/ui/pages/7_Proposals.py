"""Review LLM-generated consolidation proposals.

Reads <vault>/proposals/*.md (written by `python scripts/consolidate.py
--project <name> --write`), renders one card per proposal with a small
graph diff, and lets the reviewer Approve / Reject / Defer.

Decisions are written back to the markdown file's `status:` frontmatter
field so they survive page reloads and a re-run of the consolidator.
"""
from __future__ import annotations

import traceback
from pathlib import Path

import streamlit as st

from kgforge.engine.consolidator import (
    consolidate as run_consolidator,
    list_proposal_files,
    load_proposal_file,
    set_proposal_status,
    write_proposal_files,
)
from kgforge.project import Project
from kgforge.ui.helpers import api_key_warning, project_chip, require_project

# ── Page setup ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Proposals · kgforge", layout="wide")
project_chip()
api_key_warning()

project = require_project()
project.ensure_dirs()

st.title("🪶 Proposals")
st.caption(
    f"Project: **{project.label}** · "
    f"reviewing consolidation proposals in `{project.vault_dir.name}/proposals/`"
)

# ── Run consolidator on demand ───────────────────────────────────────────────

with st.container(border=True):
    cols = st.columns([3, 1])
    with cols[0]:
        st.markdown(
            "**Run the consolidator** to scan the vault and propose merges, "
            "regroupings, hierarchy links, and label rewrites. Existing "
            "decisions (approved / rejected) are preserved on re-run."
        )
    with cols[1]:
        if st.button("🤖 Run consolidator", type="primary", width="stretch"):
            with st.status("Calling the consolidator…", expanded=False) as status:
                try:
                    proposals = run_consolidator(project.vault_dir, project.pack)
                    paths = write_proposal_files(
                        proposals, project.vault_dir,
                        model_snapshot=project.pack.models.ask,
                    )
                    status.update(
                        label=f"Wrote {len(paths)} proposal(s)",
                        state="complete",
                    )
                    st.rerun()
                except Exception as exc:
                    status.update(label="Failed", state="error")
                    st.error(str(exc))
                    st.code(traceback.format_exc())


# ── Helpers ──────────────────────────────────────────────────────────────────


def _wiki_to_id(value) -> str:
    s = str(value).strip()
    if s.startswith("[[") and s.endswith("]]"):
        return s[2:-2]
    return s


def _graph_for(meta: dict) -> str | None:
    """Return a DOT-string mini graph diff for a proposal, or None if N/A.

    Convention: green dashed = node/edge being added; red dotted with strikethrough
    label = node being removed; black = unchanged context.
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
            '}\n'
        )
    if op == "group_codes":
        parent = meta.get("parent_theme_id", "parent_theme")
        new_label = meta.get("new_subtheme_label", "new subtheme")
        members = meta.get("member_code_ids") or []
        lines = [
            "digraph G {\n",
            '  node [shape=box, style=rounded];\n',
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
            '}\n'
        )
    if op == "rename_label":
        eid = meta.get("entity_id", "entity")
        new_label = meta.get("new_label", "?")
        return (
            "digraph G {\n"
            '  node [shape=box, style=rounded];\n'
            f'  "{eid}" [label=<{eid}<BR/><FONT POINT-SIZE="10" COLOR="darkgreen">'
            f'label → {new_label}</FONT>>];\n'
            '}\n'
        )
    return None


OP_TITLE = {
    "merge_entities":  "🔗 Merge",
    "group_codes":     "📚 Group codes",
    "link_hierarchy":  "➡ Link hierarchy",
    "rename_label":    "✏ Rename",
}

STATUS_BADGE = {
    "pending":  "🟡 pending",
    "approved": "🟢 approved",
    "rejected": "🔴 rejected",
    "deferred": "⏸ deferred",
}

CONFIDENCE_BADGE = {
    "high":   "🔵 high",
    "medium": "🟣 medium",
    "low":    "⚪ low",
}


def _render_payload_summary(meta: dict) -> str:
    op = meta.get("operation")
    if op == "merge_entities":
        return (f"Keep **`{meta.get('kept_id')}`**, "
                f"remove `{meta.get('removed_id')}`")
    if op == "group_codes":
        members = meta.get("member_code_ids") or []
        return (f"New Subtheme **{meta.get('new_subtheme_label')!r}** "
                f"under `{meta.get('parent_theme_id')}` "
                f"({len(members)} member code(s))")
    if op == "link_hierarchy":
        return (f"`{meta.get('from_id')}` —**{meta.get('property')}**→ "
                f"`{meta.get('to_id')}`")
    if op == "rename_label":
        return (f"`{meta.get('entity_id')}` → label **{meta.get('new_label')!r}**")
    return str(meta.get("operation", "?"))


def _render_card(path: Path, project: Project) -> None:
    meta = load_proposal_file(path)
    if not meta:
        st.caption(f"⚠ {path.name}: no frontmatter")
        return

    op = meta.get("operation", "?")
    status = meta.get("status", "pending")
    confidence = meta.get("confidence", "medium")
    pid = meta.get("proposal_id", path.stem)

    header = (
        f"{OP_TITLE.get(op, op)}  ·  "
        f"{STATUS_BADGE.get(status, status)}  ·  "
        f"{CONFIDENCE_BADGE.get(confidence, confidence)}  ·  "
        f"`{pid}`"
    )

    with st.expander(header, expanded=(status == "pending")):
        st.markdown(_render_payload_summary(meta))

        dot = _graph_for(meta)
        if dot:
            st.graphviz_chart(dot, use_container_width=True)

        st.markdown("**Rationale**")
        st.markdown(f"> {meta.get('rationale', '_(none)_')}")

        evidence = meta.get("evidence") or []
        if evidence:
            st.markdown("**Evidence**")
            for q in evidence:
                st.markdown(f"> {q}")

        notes_key = f"notes_{pid}"
        notes = st.text_area(
            "Reviewer notes (optional)",
            value=meta.get("reviewer_notes", "") or "",
            key=notes_key,
            height=70,
        )

        cols = st.columns([1, 1, 1, 4])
        with cols[0]:
            if st.button("✅ Approve", key=f"app_{pid}",
                         type="primary", width="stretch"):
                set_proposal_status(path, "approved", reviewer_notes=notes)
                st.toast("Approved", icon="✅")
                st.rerun()
        with cols[1]:
            if st.button("❌ Reject", key=f"rej_{pid}", width="stretch"):
                set_proposal_status(path, "rejected", reviewer_notes=notes)
                st.toast("Rejected", icon="❌")
                st.rerun()
        with cols[2]:
            if st.button("⏸ Defer", key=f"def_{pid}", width="stretch"):
                set_proposal_status(path, "deferred", reviewer_notes=notes)
                st.toast("Deferred")
                st.rerun()

        st.caption(f"_{path.relative_to(project.vault_dir)}_")


# ── Queue render ─────────────────────────────────────────────────────────────


paths = list_proposal_files(project.vault_dir)
if not paths:
    st.info(
        "No proposals yet. Click **Run consolidator** above (or run "
        "`python scripts/consolidate.py --project "
        f"{project.name} --write` from the CLI)."
    )
    st.stop()

# Group by status; pending first.
by_status: dict[str, list[Path]] = {"pending": [], "approved": [],
                                    "rejected": [], "deferred": []}
for p in paths:
    meta = load_proposal_file(p) or {}
    s = meta.get("status", "pending")
    by_status.setdefault(s, []).append(p)

counts = {k: len(v) for k, v in by_status.items()}
st.write(
    f"**{counts['pending']}** pending · "
    f"{counts['approved']} approved · "
    f"{counts['rejected']} rejected · "
    f"{counts['deferred']} deferred"
)

if any(by_status[k] for k in ("approved", "rejected", "deferred")) and \
   counts["approved"] > 0:
    st.success(
        f"{counts['approved']} approved proposal(s) ready to apply. "
        "Run `python scripts/apply_proposals.py --project "
        f"{project.name}` to write them to the vault."
    )

for status_key in ("pending", "deferred", "approved", "rejected"):
    bucket = by_status[status_key]
    if not bucket:
        continue
    st.subheader(f"{STATUS_BADGE[status_key]} ({len(bucket)})")
    for p in bucket:
        _render_card(p, project)
