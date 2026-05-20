"""Help — what callimachus is for, how to use it, and how to recover when it breaks.

Navigation is two-level: tabs across the top, expanders inside each tab.
Nothing here requires a project to be loaded, so the page is reachable from
a fresh install.
"""
from __future__ import annotations

import streamlit as st

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

st.set_page_config(page_title="Help · Callimachus", layout="wide")
project_chip()

st.title("❓ Help")
st.caption("What callimachus is for · how a typical session flows · what each page does · how to fix common problems.")

overview, workflow, concepts, pages_tab, troubleshooting = st.tabs(
    ["Overview", "Workflow", "Concepts", "Pages", "Troubleshooting"]
)

# ── Overview ─────────────────────────────────────────────────────────────────
with overview:
    st.subheader("What is callimachus?")
    st.markdown(
        "callimachus turns **PDFs of structured documents** (statutes, standards, "
        "policies) into a **queryable knowledge graph** that a human still "
        "controls. An LLM proposes entities; a person approves them; the "
        "graph is rebuilt from the approved set. Nothing reaches the graph "
        "without a review step."
    )

    with st.expander("Who is it for?", expanded=False):
        st.markdown(
            "- **Ontology engineers** building a domain ontology against a "
            "real corpus instead of in the abstract.\n"
            "- **Compliance / legal researchers** who need to ask "
            "cross-document questions over jurisdictional text.\n"
            "- **Anyone** evaluating whether an LLM can be trusted to "
            "populate a schema, by keeping the human in the loop on every "
            "submission."
        )

    with st.expander("How is it different from just prompting an LLM?", expanded=False):
        st.markdown(
            "- The schema (classes, properties, IRIs, prompts, queries) is "
            "**declarative** — defined once in a *pack*, reused across "
            "projects.\n"
            "- Extracted entities land in a **vault** of Markdown+YAML "
            "files, not opaque JSON — you can read, edit, and `git diff` "
            "them.\n"
            "- The graph is rebuilt from the vault, so the **source of "
            "truth is the files**, not the model output.\n"
            "- Natural-language questions are answered by **synthesising "
            "SPARQL** and executing it — answers are grounded in triples, "
            "with citations back to the vault entries that produced them."
        )

    with st.expander("What's bundled out of the box?", expanded=False):
        st.markdown(
            "A **compliance pack** covering the Jamaica Data Protection Act "
            "2020 — classes for `Statute`, `Provision`, `Definition`, "
            "`Regulator`, `Obligation`, plus three competency questions and "
            "a hand-curated seed of eight entities. Use it as-is, or create "
            "a blank project from the **Projects** page and define your own "
            "pack."
        )

# ── Workflow ─────────────────────────────────────────────────────────────────
with workflow:
    st.subheader("A typical session")
    st.caption("Step through these in order the first time. Later sessions you'll mostly live on the Dashboard and Query pages.")

    with st.expander("1 — Open or create a project", expanded=True):
        st.markdown(
            "Go to **Projects** in the sidebar. Either:\n\n"
            "- Open the bundled `compliance` project to try the DPA 2020 "
            "demo, or\n"
            "- Create a new project from the `blank` template and point it "
            "at your own pack.\n\n"
            "The active project name shows in the sidebar chip on every "
            "page."
        )

    with st.expander("2 — Confirm your API key", expanded=False):
        st.markdown(
            "Extraction and natural-language queries call the Anthropic "
            "API. Set `ANTHROPIC_API_KEY`:\n\n"
            "- in a `.env` file at the repo root (recommended — survives "
            "restarts), **or**\n"
            "- on the **Settings** page for this session only.\n\n"
            "If the key is missing, a yellow banner appears on every page "
            "and LLM calls will fail."
        )

    with st.expander("3 — Drop a PDF and extract", expanded=False):
        st.markdown(
            "On **Dashboard**:\n\n"
            "1. **Drop documents** — upload one or more PDFs (or whatever "
            "extensions the active pack accepts).\n"
            "2. **Process all** — the engine runs Docling/pdfplumber → "
            "Claude → JSON-Schema-validated entities, writing one Markdown "
            "file per entity into the project's `vault/` directory and a "
            "*pending submission* into the approval backend.\n"
            "3. Each file extracted gets its own card under **Pending "
            "review**."
        )

    with st.expander("4 — Review and approve", expanded=False):
        st.markdown(
            "Each pending submission shows the entity cards the model "
            "proposed — class, label, source page, source text snippet, and "
            "properties. Click:\n\n"
            "- **✅ Approve** to commit the entities into the vault (and, "
            "if the project uses the git backend, to merge the proposal "
            "branch).\n"
            "- **❌ Reject** to drop the submission.\n\n"
            "Approval is per-document, not per-entity — reject and re-run "
            "if the model got a single entity badly wrong, or edit the "
            "vault file directly after approval."
        )

    with st.expander("5 — Inspect the schema (optional)", expanded=False):
        st.markdown(
            "The **Schema** page shows the active pack's classes, "
            "properties, prompt template, and IRI namespaces. Use it to "
            "double-check that the model is being asked the right "
            "questions before you bulk-process a corpus."
        )

    with st.expander("6 — Query the graph", expanded=False):
        st.markdown(
            "On **Query**:\n\n"
            "- **Competency questions** — pre-canned SPARQL queries shipped "
            "with the pack. One click runs them against the current vault.\n"
            "- **Natural language** — type a question; Claude synthesises "
            "SPARQL using the schema + entity catalog as context, runs it, "
            "and summarises the rows with citations back to vault files.\n"
            "- Use **Show SPARQL** to see and tune the query the model "
            "generated."
        )

# ── Concepts ─────────────────────────────────────────────────────────────────
with concepts:
    st.subheader("Concepts you'll see referenced")
    st.caption("Read these once; the rest of the UI assumes you know them.")

    with st.expander("Pack", expanded=False):
        st.markdown(
            "A **pack** is the declarative bundle of everything that "
            "defines a *domain*: the OWL schema (`schema.ttl`), the prompt "
            "template, IRI namespaces, accepted file extensions, and the "
            "pre-canned SPARQL competency questions. Packs live under "
            "`callimachus/pack/builtin/` (or any path you point at). One pack "
            "can drive many projects."
        )

    with st.expander("Project", expanded=False):
        st.markdown(
            "A **project** binds a pack to a concrete working directory: "
            "its `vault/` (extracted entities), `inbox/` (PDFs waiting to "
            "be processed), `sources/` (originals), and an approval "
            "backend. Switch projects to switch corpora without touching "
            "the schema."
        )

    with st.expander("Vault", expanded=False):
        st.markdown(
            "The **vault** is the directory of approved entity files — one "
            "Markdown + YAML frontmatter file per entity. This is the "
            "source of truth. The Turtle graph (`vault.ttl`) is "
            "**regenerated** from the vault, so anything you change in a "
            "vault file flows through to the next query."
        )

    with st.expander("Approval backend", expanded=False):
        st.markdown(
            "How proposed entities get from *extracted* to *in the vault*. "
            "Two backends ship today:\n\n"
            "- **filesystem** (default) — pending submissions live in a "
            "staging dir; approve copies them into the vault.\n"
            "- **git** — each submission is a proposal branch with a "
            "diffable commit; approve merges to `main`. Use this when you "
            "want PR-style review and history."
        )

    with st.expander("Competency question (CQ)", expanded=False):
        st.markdown(
            "A SPARQL query the pack guarantees the graph can answer. CQs "
            "are the acceptance test for the ontology — if a CQ breaks "
            "after a schema change, the change isn't ready. They also "
            "double as worked examples for the natural-language agent."
        )

# ── Pages ────────────────────────────────────────────────────────────────────
with pages_tab:
    st.subheader("What each page is for")

    with st.expander("🏠 Home", expanded=False):
        st.markdown(
            "Landing page. Shows the active project and a summary of its "
            "pack and approval backend. Use the sidebar to navigate."
        )

    with st.expander("📁 Projects", expanded=False):
        st.markdown(
            "List existing projects, create one from a template "
            "(`compliance` or `blank`), and set the active project. "
            "Switching project here changes which vault and pack every "
            "other page operates on."
        )

    with st.expander("📊 Dashboard", expanded=False):
        st.markdown(
            "The day-to-day workspace:\n\n"
            "1. **Drop documents** — upload PDFs into the inbox.\n"
            "2. **Inbox** — see what's queued; **Process all** runs "
            "extraction.\n"
            "3. **Pending review** — approve or reject each submission."
        )

    with st.expander("🧬 Schema", expanded=False):
        st.markdown(
            "Read-only view of the active pack — classes, properties, "
            "prompt template, namespaces. Useful when debugging why the "
            "model extracted (or didn't extract) something."
        )

    with st.expander("🔎 Query", expanded=False):
        st.markdown(
            "Run pre-canned competency questions or ask natural-language "
            "questions. Both produce SPARQL + a result table; NL questions "
            "additionally get a prose summary with vault citations."
        )

    with st.expander("⚙ Settings", expanded=False):
        st.markdown(
            "Set the Anthropic API key, default extraction/query models, "
            "and the project root directory. Settings persist via `.env`."
        )

# ── Troubleshooting ──────────────────────────────────────────────────────────
with troubleshooting:
    st.subheader("When something doesn't work")

    with st.expander("\"ANTHROPIC_API_KEY is not set\" banner won't go away", expanded=False):
        st.markdown(
            "Streamlit only reads `.env` at process start. If you just "
            "added the key:\n\n"
            "1. Stop the server (`Ctrl+C` in the terminal running "
            "Streamlit).\n"
            "2. Confirm the key is in `.env` at the repo root, on its own "
            "line: `ANTHROPIC_API_KEY=sk-ant-…`\n"
            "3. Restart with `streamlit run callimachus/ui/app.py` (or "
            "`python -m streamlit run …`)."
        )

    with st.expander("\"No project selected\" / pages keep nudging me to Projects", expanded=False):
        st.markdown(
            "The active project is stored in session state and resets when "
            "the browser tab is closed. Open **Projects** and click into "
            "the project you want — the sidebar chip should then show its "
            "name on every page."
        )

    with st.expander("`ModuleNotFoundError: No module named 'callimachus'`", expanded=False):
        st.markdown(
            "Streamlit is running under a Python that doesn't have "
            "`callimachus` installed — usually a global Python rather than the "
            "venv. From the activated venv:\n\n"
            "```\n"
            "pip install -e \".[ui]\"\n"
            "python -m streamlit run callimachus/ui/app.py\n"
            "```\n\n"
            "`python -m streamlit` bypasses any global `streamlit.exe` "
            "that may be earlier on `PATH`."
        )

    with st.expander("Extraction fails on a specific PDF", expanded=False):
        st.markdown(
            "Common causes:\n\n"
            "- **Scanned/image-only PDF** — pdfplumber and Docling both "
            "need a text layer. Run OCR (Tesseract, ABBYY, etc.) "
            "beforehand.\n"
            "- **Rate-limit / 529 from Anthropic** — wait and retry the "
            "single file rather than re-running the whole inbox.\n"
            "- **Schema mismatch** — check the **Schema** page; if the "
            "pack expects classes the document doesn't contain, the model "
            "may return an empty extraction. That's a pack problem, not a "
            "callimachus bug."
        )

    with st.expander("Approved entities don't show up in Query results", expanded=False):
        st.markdown(
            "The graph is rebuilt from the vault on each query — but only "
            "if the vault is reachable from the project's `vault_dir`. "
            "Double-check on **Projects** that the project points at the "
            "directory you expect, and that approved files are in it (not "
            "in a stale `pending/` or `proposals/` directory)."
        )

    with st.expander("Need to start over for one document", expanded=False):
        st.markdown(
            "1. Delete the vault files for that `doc_id` (the **Dashboard** "
            "card shows the file list).\n"
            "2. Move the PDF back from `sources/` to `inbox/`.\n"
            "3. Click **Process all** again on the Dashboard."
        )

# ── Footer hint ──────────────────────────────────────────────────────────────
st.divider()
project = get_active_project()
if project is None:
    st.info("Tip: open a project on the **Projects** page to unlock the Dashboard, Schema, and Query pages.")
else:
    st.caption(f"Active project: **{project.label}** (`{project.name}`)")
