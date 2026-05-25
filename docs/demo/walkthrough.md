# Callimachus thematic walkthrough — narrator script

Pairs with the live UI screencast. ~2 minutes, five views, one live LLM call.

## What this is

Callimachus turns documents into typed, queryable knowledge graphs. The `thematic` project shows the platform doing **qualitative coding**: interview transcripts → codes → subthemes → themes, with verbatim provenance back to speaker turns. Every proposed change to the graph (a merge, a re-label, a hierarchy edit) arrives as a **reviewable artifact** that a human approves or rejects — nothing lands in the canonical vault unattended.

Three real frontend bugs were caught during the first take and fixed before this one. You'll see all three working on camera.

## Setup

```powershell
git clone https://github.com/elroy-galbraith/callimachus.git
cd callimachus
python -m venv .venv ; .\.venv\Scripts\activate
pip install -e .[api]
# create .env at repo root: ANTHROPIC_API_KEY=... and/or GEMINI_API_KEY=...
uvicorn callimachus.api.main:app --port 8000
# second terminal
cd frontend ; npm install ; npm run dev
# browser → http://localhost:5173
```

## The walkthrough

### 1 · Projects list — `/projects`

Three shipped projects: **compliance** (Caribbean data-protection law), **densho_themes** (real Densho Digital Archive oral histories), **thematic** (the synthetic interview transcripts we're touring).

> Same engine, three corpora, three packs. A pack is just a YAML schema + SPARQL queries + a prompt template. Schema changes don't require code changes.

### 2 · Thematic Dashboard

Open `thematic`. Three-step pipeline:

- **1 — Drop documents** (`.pdf` / `.txt` / `.md` / `.vtt`)
- **2 — Inbox** — uploaded docs awaiting `Process all`
- **3 — Pending review** — extracted entities awaiting human OK

> Documents come in here, get processed by an LLM extractor, and land as pending entities. Nothing touches the canonical vault until you approve it.

### 3 · Schema page

Underlying ontology: 4 classes (Theme, Subtheme, Code, Excerpt), 4 properties (hasSubtheme, codedAs, supportsTheme, spokenBy), 3 competency questions, and a model picker.

Both model fields show **ANTHROPIC CLAUDE KEY SET** badges (green) — the env loader is finding the key in `.env`.

> The pack picks any LiteLLM-supported provider — Anthropic, OpenAI, Gemini, Mistral, Cohere, Together, Bedrock. We just merged a fix for a Windows footgun where an empty shell var was shadowing `.env`; that's why the green badge here is itself a "demonstrates the fix" moment.

🔧 **Fix on camera:** [PR #10](https://github.com/elroy-galbraith/callimachus/pull/10) — API scrubs empty-string provider keys from `os.environ` before `load_dotenv`, so a stray `ANTHROPIC_API_KEY=""` in the shell no longer wins over the real value in `.env`.

### 4 · Proposals

Three pending consolidation proposals from a prior LLM run, each with its own visual mini-graph:

- **Link hierarchy** (low confidence) — link `Distrust of Institutions` to subtheme `Lack of Transparency` via `hasSubtheme`. Two boxes, dashed green arrow.
- **Group codes** (high confidence) — create a new `Institutional Opacity` subtheme grouping two existing codes. The graph shows the new subtheme parented under its theme, with implied edges down to the codes.
- **Merge entities** (medium confidence) — collapse `Feeling shut out` into `Lack of transparency`. Full rationale + two evidence excerpts.

Every card has Approve / Reject / Defer. Approval rewrites the wikilinks across the vault and deletes the merged file; rejection leaves an audit trail.

> Each proposal is a markdown file in `vault/proposals/`. The mutation is the file. Approving it is a deterministic graph rewrite — no LLM in the loop at apply time.

🔧 **Fix on camera:** [PR #12](https://github.com/elroy-galbraith/callimachus/pull/12) — `ProposalMiniGraph` stops racing React's reconciler. Before the fix, every card showed a red "mini graph failed to render — `removeChild` on Node" error; now they render the actual SVGs.

### 5 · Query → Ask (natural language)

Three tabs: **Competency questions** (pre-canned SPARQL the pack ships), **Ask (natural language)** (LLM-synthesized SPARQL), **Custom SPARQL** (raw).

Click **Ask (natural language)** and type:

> *Which themes have been identified, and how many excerpts support each?*

Side panel streams the pipeline as SSE events — vault.ttl rebuild → graph load into pyoxigraph → catalog build → **SPARQL synthesis via `claude-sonnet-4-6`** → execute → 2 rows → summarize. ~10 seconds end to end.

Main view fills in:
- **Rationale** — why it chose this query
- **Generated SPARQL** — a clean `SELECT … COUNT(DISTINCT ?excerpt) … OPTIONAL { … tha:supportsTheme ?theme } GROUP BY … ORDER BY`
- **Intermediate result** — 2-row table with theme IRIs and counts
- **Answer** — markdown with wikilinks back into the vault:
  > Two themes have been identified in the dataset:
  > - **Distrust of Institutions** — supported by 3 excerpts
  > - **Loss of Control** — supported by 3 excerpts
  >
  > Both themes are equally well-evidenced, each drawing on three distinct excerpts.

> The model picks the right predicate, wraps the count in OPTIONAL so empty themes still appear, and links its answer back to the source vault files. The whole pipeline is observable — SPARQL, intermediate rows, and final summary all visible side by side.

🔧 **Fix on camera:** [PR #11](https://github.com/elroy-galbraith/callimachus/pull/11) — frontend now invalidates the job query on SSE end + on SSE connection error. Before the fix, the cache lagged the stream and the Answer card never rendered even though the pipeline reached `finished`.

## After the demo

- **CLI** version of the same flow: `python scripts/ask.py "question" --show-sparql --pack thematic`
- **Custom pack** — copy `callimachus/pack/builtin/thematic/` as a starting point, edit `pack.yaml`, point a new project at it. No code changes.
- **Compliance pack** (`/projects/compliance`) — same engine, git-backed approval flow (mutations land as PRs) instead of filesystem audit.
- **Densho project** (`/projects/densho_themes`) — same engine on real-world data, Kara Kondo's interview from the Densho Digital Archive.

## What to point out if asked

- **No vector DB** — everything is RDF + SPARQL. The "intelligence" is the LLM choosing the query, not similarity search over chunks.
- **Provenance all the way down** — every Excerpt cites `source_section` ("Interview 03 / 14:22") and `spokenBy` ("P03"). When the system says "supported by 3 excerpts," you can click straight to the verbatim quotes.
- **Human in the loop is the default** — proposals stay pending until a human approves. The system can run unsupervised on extraction (we trust LLMs to find candidate entities) but never on consolidation (we don't trust them to decide what to merge).
- **Three bugs caught + shipped between takes** — the green badges, rendered mini-graphs, and rendered Answer card are all things that were broken in the first take. PR numbers are above; the fixes are tiny and worth a read.
