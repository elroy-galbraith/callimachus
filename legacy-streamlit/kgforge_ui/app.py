"""kgforge — Streamlit landing page (legacy).

Superseded by the React + FastAPI frontend at ../frontend/. This page is
kept runnable for reference and as a fallback during the cutover.

Run with:
    streamlit run legacy-streamlit/kgforge_ui/app.py
"""
from __future__ import annotations

# Bootstrap: put ``legacy-streamlit/`` on sys.path so
# ``from kgforge_ui.helpers import ...`` resolves whether Streamlit
# launched this file directly or via a deep-link to a /pages/ subpage.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

import streamlit as st

from kgforge_ui.helpers import api_key_warning, get_active_project, project_chip

st.set_page_config(
    page_title="kgforge",
    page_icon="🛠",
    layout="wide",
    initial_sidebar_state="expanded",
)

project_chip()
api_key_warning()

st.title("🛠 kgforge")
st.caption("Configurable PDF → typed-entities → graph → query platform.")

st.markdown(
    """
A *project* binds a **pack** (declarative schema, prompts, IRIs, queries) to
a **vault** (the extracted entity files) and an **approval workflow**
(filesystem-default or git for the existing compliance demo).

Use the navigation in the sidebar:

| Page | Use it for |
| --- | --- |
| **Projects** | List existing projects · create one from a template (compliance / blank) · open one |
| **Dashboard** | Upload a PDF, run extraction, review/approve the entities the model proposed |
| **Schema** | Inspect the active pack — classes, properties, prompt template, namespaces |
| **Query** | Run pre-canned competency questions; ask natural-language questions over the graph |
| **Settings** | API key, default models, project root |
    """
)

project = get_active_project()
if project:
    st.success(f"Active project: **{project.label}** (`{project.name}`)")
    st.write(
        f"- **Vault:** `{project.vault_dir}`\n"
        f"- **Inbox:** `{project.inbox_dir}` "
        f"({'exists' if project.has_inbox else 'will be created on first upload'})\n"
        f"- **Approval:** `{project.approval_config.get('backend', 'filesystem')}`\n"
        f"- **Pack:** `{project.pack.metadata.name}` "
        f"({len(project.pack.classes)} classes, {len(project.pack.properties)} properties, "
        f"{len(project.pack.competency_questions)} CQs)"
    )
else:
    st.info(
        "No project loaded. Head to **Projects** in the sidebar to "
        "open the bundled compliance project or create a new one."
    )
