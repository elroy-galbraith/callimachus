"""Projects page — list, open, create."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from kgforge.pack.loader import BUILTIN_DIR
from kgforge.project import create_from_template, list_projects
# Bootstrap: ensure ``kgforge_ui`` resolves when Streamlit deep-links
# directly to this page without running app.py first.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

from kgforge_ui.helpers import get_active_project, project_chip

st.set_page_config(page_title="Projects · kgforge", layout="wide")
project_chip()

st.title("📂 Projects")
st.caption("Each project binds a pack to a vault, inbox, and approval workflow.")

# ── Existing projects ────────────────────────────────────────────────────────

projects = list_projects()
if not projects:
    st.info(
        "No projects yet. Create one below — the **compliance** template "
        "matches the bundled Caribbean Compliance Ontology demo."
    )
else:
    st.subheader("Existing projects")
    for p in projects:
        is_active = st.session_state.get("project_name") == p["name"]
        cols = st.columns([4, 2, 2])
        with cols[0]:
            label = f"**{p['label']}** · `{p['name']}`"
            if is_active:
                label += " ✅"
            st.markdown(label)
            st.caption(p["dir"])
        with cols[1]:
            if st.button("Open", key=f"open_{p['name']}", disabled=is_active,
                         width="stretch"):
                st.session_state["project_name"] = p["name"]
                st.session_state.pop("_project_cache", None)
                st.rerun()
        with cols[2]:
            if is_active and st.button("Close", key=f"close_{p['name']}",
                                       width="stretch"):
                st.session_state.pop("project_name", None)
                st.session_state.pop("_project_cache", None)
                st.rerun()

active = get_active_project()
if active is not None:
    st.divider()
    st.subheader(f"Active: {active.label}")
    st.json(
        {
            "name": active.name,
            "pack": active.pack.metadata.name,
            "vault_dir": str(active.vault_dir),
            "inbox_dir": str(active.inbox_dir),
            "sources_dir": str(active.sources_dir),
            "approval": active.approval_config,
            "classes": [c.name for c in active.pack.classes],
            "properties": [p.name for p in active.pack.properties],
            "competency_questions": [cq.label for cq in active.pack.competency_questions],
        },
        expanded=False,
    )

# ── Create new project ───────────────────────────────────────────────────────

st.divider()
st.subheader("Create a new project")

# Available templates: every kgforge/pack/builtin/<name>/ that has a pack.yaml.
templates: list[str] = sorted(
    p.name for p in BUILTIN_DIR.iterdir() if (p / "pack.yaml").exists()
) if BUILTIN_DIR.exists() else []

if not templates:
    st.error("No built-in pack templates found under kgforge/pack/builtin/.")
else:
    with st.form("create_project"):
        cols = st.columns([2, 2, 2])
        with cols[0]:
            new_name = st.text_input(
                "Name",
                placeholder="my_thematic_study",
                help="Snake-case identifier; used as the folder name.",
            )
        with cols[1]:
            new_label = st.text_input(
                "Label",
                placeholder="My Thematic Study",
                help="Human-readable display name.",
            )
        with cols[2]:
            new_template = st.selectbox(
                "Template",
                options=templates,
                index=templates.index("compliance") if "compliance" in templates else 0,
                help="Copies the chosen built-in pack into the new project. "
                     "You can edit it freely without touching the bundled defaults.",
            )

        backend = st.radio(
            "Approval backend",
            options=["filesystem", "git"],
            horizontal=True,
            help=(
                "**filesystem** (recommended): in-app approve/reject; SQLite audit log. "
                "**git**: extracted entities land on a `proposals/<doc>` branch awaiting merge "
                "(matches the original carib-comp-ont workflow)."
            ),
        )

        submitted = st.form_submit_button("Create", type="primary")
        if submitted:
            if not new_name or not new_name.replace("_", "").isalnum() or not new_name[0].isalpha():
                st.error("Name must start with a letter and contain only letters, digits, underscores.")
            else:
                try:
                    project = create_from_template(
                        new_name,
                        template=new_template,
                        label=new_label or None,
                        backend=backend,
                    )
                    st.session_state["project_name"] = project.name
                    st.session_state.pop("_project_cache", None)
                    st.success(f"Created and opened project **{project.label}**.")
                    st.rerun()
                except FileExistsError:
                    st.error(f"A project named {new_name!r} already exists.")
                except Exception as exc:  # pragma: no cover  (defensive)
                    st.exception(exc)

# ── Footer hint for the bundled compliance project ───────────────────────────

if not any(p["name"] == "compliance" for p in projects) and (
    Path(__file__).resolve().parents[3] / "vault"
).exists():
    st.divider()
    st.caption(
        "💡 The bundled `compliance` project (Caribbean Compliance Ontology) "
        "should be visible above. If it isn't, ensure `projects/compliance/project.json` exists."
    )
