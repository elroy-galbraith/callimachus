"""Small helpers shared across kgforge UI pages."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Make the package importable when streamlit is launched from anywhere.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env so ANTHROPIC_API_KEY is available to engine modules. We do NOT
# pass override=True: a value already present in os.environ (set by the
# shell, a wrapper, or the Settings-page override) takes precedence over
# the .env file, matching standard dotenv conventions.
#
# Note: this differs from scripts/extractor.py and scripts/curator.py which
# DO use override=True — that's a deliberate Windows-shell workaround
# (ANTHROPIC_API_KEY can be pre-set as an empty string on Windows). The UI
# is launched with a known clean process via `streamlit run`, so the
# workaround isn't needed here.
try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from kgforge.project import Project, load_project  # noqa: E402


def get_active_project() -> Project | None:
    """Return the loaded Project for the active project_name, or None."""
    name = st.session_state.get("project_name")
    if not name:
        return None
    # Cache loaded projects on session state so we don't re-read JSON each rerun.
    cache = st.session_state.setdefault("_project_cache", {})
    if name not in cache:
        try:
            cache[name] = load_project(name)
        except Exception as e:
            st.error(f"Failed to load project {name!r}: {e}")
            return None
    return cache[name]


def require_project() -> Project:
    """Pages that need a project should call this near the top.

    Renders a friendly nudge + Stop if no project is selected.
    """
    project = get_active_project()
    if project is None:
        st.warning("No project selected — open one on the **Projects** page first.")
        st.stop()
    return project


def project_chip() -> None:
    """Small sidebar widget showing the active project."""
    project = get_active_project()
    with st.sidebar:
        if project:
            st.markdown(f"**Project:** `{project.name}`")
            st.caption(project.label)
        else:
            st.markdown("_No project loaded._")


def have_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def api_key_warning() -> None:
    if not have_api_key():
        st.warning(
            "ANTHROPIC_API_KEY is not set. LLM calls will fail. "
            "Configure it on the **Settings** page or in `.env`."
        )
