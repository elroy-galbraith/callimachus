"""Schema — read-only viewer of the active pack with live prompt preview.

Phase C ships read-only inspection. A YAML editor with validation +
diff-against-vault would be a natural Phase C.1 follow-up.
"""
from __future__ import annotations

import json

import streamlit as st

from callimachus.engine import prompt as prompt_engine
from callimachus.engine import schema_builder
# Bootstrap: ensure ``callimachus_ui`` resolves when Streamlit deep-links
# directly to this page without running app.py first.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

from callimachus_ui.helpers import project_chip, require_project

st.set_page_config(page_title="Schema · Callimachus", layout="wide")
project_chip()

project = require_project()
pack = project.pack

st.title("📐 Schema")
st.caption(f"Pack `{pack.metadata.name}` · v{pack.metadata.version}")
if pack.metadata.description:
    st.markdown(f"> {pack.metadata.description}")

# ── Namespaces ───────────────────────────────────────────────────────────────

st.subheader("Namespaces")
cols = st.columns(2)
with cols[0]:
    st.markdown(f"**Schema IRI** · `{pack.base_iri}`")
    st.markdown(f"**Prefix** · `{pack.prefix}:`")
with cols[1]:
    st.markdown(f"**Entity IRI** · `{pack.entity_iri}`")
    st.markdown(f"**Entity prefix** · `{pack.entity_prefix}:`")

# ── Classes ──────────────────────────────────────────────────────────────────

st.subheader(f"Classes ({len(pack.classes)})")
st.dataframe(
    [
        {
            "name": c.name,
            "label": c.label,
            "parent": c.parent or "—",
            "description": c.description or "",
        }
        for c in pack.classes
    ],
    hide_index=True,
    width="stretch",
)

# ── Properties ───────────────────────────────────────────────────────────────

st.subheader(f"Properties ({len(pack.properties)})")
st.dataframe(
    [
        {
            "name": p.name,
            "domain": p.domain or "any",
            "range": p.range or "any",
            "datatype?": "✓" if p.datatype else "",
            "predicate IRI": pack.property_iri(p.name),
        }
        for p in pack.properties
    ],
    hide_index=True,
    width="stretch",
)

# ── Competency questions ─────────────────────────────────────────────────────

st.subheader(f"Competency questions ({len(pack.competency_questions)})")
for cq in pack.competency_questions:
    with st.expander(f"**{cq.id}** · {cq.label}"):
        if pack.pack_dir is not None:
            qpath = pack.pack_dir / cq.file
            sparql_text = qpath.read_text(encoding="utf-8") if qpath.exists() else "(file missing)"
        else:
            sparql_text = "(no pack directory)"
        st.code(sparql_text, language="sparql")

# ── Prompt template ──────────────────────────────────────────────────────────

st.subheader("Prompt template")
st.caption(
    f"Version `{pack.prompt.version}` · text window {pack.prompt.text_window_chars} chars · "
    "renders with `{doc_id}`, `{prompt_version}`, `{few_shot}`, `{text_window}` placeholders."
)
tabs = st.tabs(["System", "User", "Few-shot", "Live preview"])

with tabs[0]:
    st.code(pack.prompt.system, language="markdown")
with tabs[1]:
    st.code(pack.prompt.user, language="markdown")
with tabs[2]:
    st.code(pack.prompt.few_shot, language="markdown")
with tabs[3]:
    sample_doc = st.text_input("Sample doc_id", "regression_doc")
    sample_version = st.text_input("Sample prompt_version", pack.prompt.version)
    sample_text = st.text_area(
        "Sample document text",
        '§2 Interpretation. "data controller" means a person who determines the purposes …',
        height=120,
    )
    if st.button("Render"):
        try:
            system, user = prompt_engine.render_prompts(
                pack, sample_doc, sample_version, sample_text
            )
            st.markdown("**System prompt:**")
            st.code(system, language="markdown")
            st.markdown("**User prompt:**")
            st.code(user, language="markdown")
        except KeyError as e:
            st.error(f"Template references missing placeholder: {e}")

# ── Generated JSON tool-use schema ───────────────────────────────────────────

st.subheader("Generated tool-use schema")
st.caption("This is what gets sent to Claude as the `extract_entities` tool's input_schema.")
schema = schema_builder.build_entity_schema(pack)
st.code(json.dumps(schema, indent=2), language="json")
