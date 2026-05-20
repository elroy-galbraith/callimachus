"""Settings — API key, model overrides, paths."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from callimachus.project import projects_dir, repo_root
# Bootstrap: ensure ``callimachus_ui`` resolves when Streamlit deep-links
# directly to this page without running app.py first.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

from callimachus_ui.helpers import get_active_project, project_chip

st.set_page_config(page_title="Settings · Callimachus", layout="wide")
project_chip()

st.title("⚙ Settings")
st.caption("Per-session overrides. To make settings persistent, edit `.env` or `pack.yaml` directly.")

# ── API key ──────────────────────────────────────────────────────────────────

st.subheader("Anthropic API key")
have = bool(os.environ.get("ANTHROPIC_API_KEY"))
st.markdown(
    f"Currently {'✅ **set**' if have else '❌ **not set**'} "
    f"({'from environment / .env' if have else 'no value'})"
)

# WARNING: this override is process-wide, not per-Streamlit-session. The
# engine's `anthropic.Anthropic()` reads ANTHROPIC_API_KEY from os.environ.
# callimachus ships with a single-user / local-desktop deployment model
# (documented in the architecture plan), so process-wide is fine here. If
# you ever expose this app to multiple users, gate this control behind
# admin auth — otherwise one user's key would be read by everyone else's
# LLM calls (and persist after they leave). The session_state copy below
# is purely so the value survives a streamlit reload of THIS page.
st.warning(
    "callimachus runs as a local single-user app. The override below is "
    "process-wide — never expose this UI to multiple users without "
    "gating this control behind authentication.",
    icon="⚠",
)
new_key = st.text_input(
    "Override (local process)",
    type="password",
    placeholder="sk-ant-…",
    value=st.session_state.get("api_key_input", ""),
    help="Sets ANTHROPIC_API_KEY for this Python process. For persistence "
         "across restarts, write it to `.env` at the repo root.",
    key="api_key_input",
)
cols = st.columns([1, 1, 4])
with cols[0]:
    if st.button("Apply", type="primary", disabled=not new_key):
        st.session_state["api_key_override"] = new_key
        os.environ["ANTHROPIC_API_KEY"] = new_key
        st.success("API key set for this process.")
        st.rerun()
with cols[1]:
    if st.button("Clear",
                 disabled="api_key_override" not in st.session_state):
        st.session_state.pop("api_key_override", None)
        # Also clear from os.environ so the next call falls back to .env / shell.
        os.environ.pop("ANTHROPIC_API_KEY", None)
        st.info("API key cleared from this process.")
        st.rerun()

# ── Active project models ────────────────────────────────────────────────────

project = get_active_project()
if project is not None:
    st.divider()
    st.subheader(f"Models · {project.label}")
    st.caption("These come from the pack. To change permanently, edit `pack.yaml`.")
    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**Extractor model:** `{project.pack.models.extractor}`")
    with cols[1]:
        st.markdown(f"**Ask model:** `{project.pack.models.ask}`")

# ── Paths ────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Paths")
st.markdown(f"**Repo root:** `{repo_root()}`")
st.markdown(f"**Projects directory:** `{projects_dir()}`")
if project is not None:
    st.markdown(f"**Active project dir:** `{project.project_dir}`")
    st.markdown(f"**Vault:** `{project.vault_dir}`")
    st.markdown(f"**Inbox:** `{project.inbox_dir}`")

# ── Pack reload ──────────────────────────────────────────────────────────────

st.divider()
st.subheader("Cache")
if st.button("🔄 Reload all packs / projects"):
    # Clear pack-loader memoisation and the per-session project cache.
    from callimachus.pack.loader import load_builtin
    load_builtin.cache_clear()
    st.session_state.pop("_project_cache", None)
    st.cache_resource.clear()
    st.success("Cleared loader caches. Reload other pages to refresh.")

# ── About ────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("About")
st.markdown(
    """
- `callimachus` v0.1.0 — see [`pyproject.toml`](.) for dependencies.
- Source: pack & engine in `callimachus/`, scripts in `scripts/`, projects in `projects/`.
- Phase status: A (config), B (engine + approval), C (UI) — current.
"""
)
