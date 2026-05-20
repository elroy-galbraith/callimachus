"""Query — competency questions + natural-language ask."""
from __future__ import annotations

import os

import streamlit as st

from callimachus.engine import ask as ask_engine
from callimachus.engine import store as store_engine
from callimachus.engine import to_turtle as to_turtle_engine
# Bootstrap: ensure ``callimachus_ui`` resolves when Streamlit deep-links
# directly to this page without running app.py first.
import sys as _sys
from pathlib import Path as _Path
for _p in _Path(__file__).resolve().parents:
    if _p.name == "legacy-streamlit":
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
        break

from callimachus_ui.helpers import api_key_warning, project_chip, require_project

st.set_page_config(page_title="Query · Callimachus", layout="wide")
project_chip()

project = require_project()
pack = project.pack

st.title("🔎 Query")
st.caption(f"Querying `{project.label}` · {len(pack.competency_questions)} competency questions")


# ── Lazy graph load ──────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading graph into Oxigraph…")
def _load_store(_schema_ttl: str, _vault_ttl: str):
    """Cache key is the (schema, vault) path pair so a project switch reloads."""
    from pathlib import Path
    paths = []
    if _schema_ttl:
        paths.append(Path(_schema_ttl))
    if _vault_ttl:
        paths.append(Path(_vault_ttl))
    return store_engine.load_store(*paths)


def _ensure_vault_ttl() -> bool:
    """Build vault.ttl from the markdown vault if missing (or stale).

    Calls the engine in-process — no subprocess, no path assumptions about
    where the app was launched from.
    """
    if not project.vault_dir.exists():
        st.error(f"Vault dir not found: {project.vault_dir}")
        return False
    vault_ttl = project.vault_ttl
    if vault_ttl.exists():
        return True
    st.info("Building vault.ttl from vault/*.md…")
    try:
        turtle = to_turtle_engine.build_turtle(project.vault_dir, project.pack)
        vault_ttl.parent.mkdir(parents=True, exist_ok=True)
        vault_ttl.write_text(turtle, encoding="utf-8")
        return True
    except Exception as exc:
        st.exception(exc)
        return False


col_rebuild, col_info = st.columns([1, 5])
with col_rebuild:
    if st.button("🔄 Rebuild vault.ttl"):
        if project.vault_ttl.exists():
            project.vault_ttl.unlink()
        _load_store.clear()
        st.rerun()
with col_info:
    if project.vault_ttl.exists():
        st.caption(f"vault.ttl · {project.vault_ttl.stat().st_size:,} bytes")

# ── Tabs ─────────────────────────────────────────────────────────────────────

cq_tab, ask_tab, sparql_tab = st.tabs([
    "🎯 Competency questions",
    "💬 Ask (natural language)",
    "✏ Custom SPARQL",
])

# ── Tab 1: pre-canned competency questions ───────────────────────────────────

with cq_tab:
    if not pack.competency_questions:
        st.info("This pack defines no competency questions.")
    else:
        labels = [cq.label for cq in pack.competency_questions]
        choice_idx = st.selectbox(
            "Question",
            options=range(len(labels)),
            format_func=lambda i: labels[i],
            key="cq_pick",
        )
        cq = pack.competency_questions[choice_idx]
        if pack.pack_dir is None:
            st.error("Pack has no resolved directory; can't load SPARQL files.")
        else:
            qpath = pack.pack_dir / cq.file
            if not qpath.exists():
                # Compliance-project fallback: sparql files live in repo root sparql/.
                if project.sparql_dir is not None:
                    qpath = project.sparql_dir / qpath.name
            if not qpath.exists():
                st.error(f"SPARQL file not found for {cq.id}: {cq.file}")
            else:
                sparql = qpath.read_text(encoding="utf-8")
                with st.expander("SPARQL", expanded=False):
                    st.code(sparql, language="sparql")
                if st.button("▶ Run", type="primary", key=f"run_cq_{cq.id}"):
                    if not _ensure_vault_ttl():
                        st.stop()
                    try:
                        store = _load_store(
                            str(project.schema_ttl) if project.schema_ttl else "",
                            str(project.vault_ttl),
                        )
                        results = ask_engine.run_sparql(store, sparql)
                        if results["kind"] == "select":
                            if results["rows"]:
                                st.dataframe(results["rows"], width="stretch")
                                st.caption(f"{len(results['rows'])} row(s)")
                            else:
                                st.info("No rows.")
                        elif results["kind"] == "ask":
                            st.success(f"ASK → {results['value']}")
                        else:
                            st.code("\n".join(results["triples"]), language="text")
                    except Exception as exc:
                        st.exception(exc)

# ── Tab 2: natural-language ask ──────────────────────────────────────────────

with ask_tab:
    api_key_warning()
    question = st.text_input(
        "Question",
        placeholder="What does the DPA say about biometric data?",
        key="nl_question",
    )
    show_sparql = st.checkbox("Show generated SPARQL + intermediate result table", value=True)
    model = st.text_input("Model", value=pack.models.ask)

    if st.button("💬 Ask", type="primary", key="run_ask",
                 disabled=not (question and os.environ.get("ANTHROPIC_API_KEY"))):
        if not _ensure_vault_ttl():
            st.stop()
        try:
            import anthropic
            client = anthropic.Anthropic()
            store = _load_store(
                str(project.schema_ttl) if project.schema_ttl else "",
                str(project.vault_ttl),
            )
            schema_text = (
                project.schema_ttl.read_text(encoding="utf-8")
                if project.schema_ttl and project.schema_ttl.exists()
                else "(no schema TTL)"
            )
            catalog = ask_engine.entity_catalog(store, pack)
            examples = ask_engine.few_shot_examples(pack)

            with st.status("Synthesising SPARQL…", expanded=False):
                sparql, rationale = ask_engine.synthesize_sparql(
                    client, model, question, schema_text, catalog, examples
                )
            if show_sparql:
                st.markdown(f"**Rationale:** {rationale}")
                st.code(sparql, language="sparql")

            with st.status("Executing query…", expanded=False):
                results = ask_engine.run_sparql(store, sparql)
            if show_sparql and results["kind"] == "select":
                st.dataframe(results.get("rows") or [], width="stretch")

            with st.status("Summarising…", expanded=False):
                answer = ask_engine.summarise(
                    client, model, question, sparql, rationale, results
                )
            st.markdown("### Answer")
            st.markdown(answer)
        except Exception as exc:
            st.exception(exc)

# ── Tab 3: free-form SPARQL ──────────────────────────────────────────────────

with sparql_tab:
    sparql_text = st.text_area(
        "SPARQL query",
        value="PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
              "SELECT ?s ?label WHERE { ?s rdfs:label ?label } LIMIT 25",
        height=180,
        key="custom_sparql",
    )
    if st.button("▶ Run SPARQL", type="primary", key="run_custom"):
        if not _ensure_vault_ttl():
            st.stop()
        try:
            store = _load_store(
                str(project.schema_ttl) if project.schema_ttl else "",
                str(project.vault_ttl),
            )
            results = ask_engine.run_sparql(store, sparql_text)
            if results["kind"] == "select":
                st.dataframe(results.get("rows") or [], width="stretch")
                st.caption(f"{len(results.get('rows') or [])} row(s)")
            elif results["kind"] == "ask":
                st.success(f"ASK → {results['value']}")
            else:
                st.code("\n".join(results["triples"]), language="text")
        except Exception as exc:
            st.exception(exc)
