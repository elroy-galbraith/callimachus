# Changelog

All notable changes to Callimachus are recorded here, newest first.
Format loosely follows [Keep a Changelog](https://keepachangelog.com);
the project does not yet follow strict semver — versions will land when
something visible to users or downstream packs changes.

---

## 2026-05-20 — Platform pivot: renamed to Callimachus

The repo started life as `carib-comp-ont` — a single-statute prototype
for extracting the Jamaica Data Protection Act 2020 into a queryable RDF
graph, complementary to Donalds, Barclay & Osei-Bryson (2023). As the
work generalised to handle qualitative interview transcripts (the
Densho oral histories) and literature reviews (legal ontologies), the
compliance work became one project among several. The old name stopped
fitting.

Picked **Callimachus** after Callimachus of Cyrene (310–240 BCE),
librarian-scholar at Alexandria, author of the *Pinakes* — the first
systematic catalog of a knowledge collection. He didn't write the books;
he made them findable. Same posture as this tool.

### Changed
- Python package `kgforge/` → `callimachus/` (every file tracked as a
  rename in git history).
- `legacy-streamlit/kgforge_ui/` → `legacy-streamlit/callimachus_ui/`.
- All imports across api, engine, project, pack, approval, tests,
  scripts, and the legacy Streamlit bootstrap.
- `pyproject.toml`: package name, `packages.find`, `package-data`, and
  the six CLI entry points (`kgforge-extract` → `callimachus-extract`).
- Frontend product name in `<title>`, `RootShell`, `ProjectShell`,
  HelpPage. `package.json` name + dev:api command.
- README rewritten platform-first. The DPA-2020 deep dive is now a brief
  Origin section that credits the carib-comp-ont starting point.

### Added
- `CHANGELOG.md` (this file).

### Notes
- GitHub repo rename (`carib-comp-ont` → `callimachus`) is still a
  manual follow-up via Settings. GitHub redirects the old URL so
  outreach links keep working.
- Memory file index now references the new project name.

---

## 2026-05-20 — Streamlit → React + FastAPI refactor

The Streamlit app (then `kgforge.ui`) had carried the project from
single-statute demo through three shipped projects, but it was hitting
the usual single-process, blocking-call, no-typed-API limits. Swapped
it for a FastAPI service wrapping the engine plus a React + Mantine
frontend consuming it. The engine, project, pack, and approval packages
were not touched — this was a presentation-layer swap.

Five-commit PR (#7), merged via rebase to preserve per-phase history.
A simplify pass + a hardening pass landed on top.

### Added
- `kgforge/api/` (now `callimachus/api/`): 8 routers, 18 routes,
  Pydantic models per domain, in-process `JobRegistry` with SSE
  streaming at `/api/jobs/{id}/events`, per-project pyoxigraph store
  cache with mtime-keyed invalidation.
- `frontend/`: Vite + React 18 + TypeScript + Mantine v7 + TanStack
  Query + React Router; seven pages with full parity to the Streamlit
  pages; lazy-loaded WASM Graphviz for proposal mini-graphs.
- `tests/api/`: 31 shape-only smoke tests via FastAPI's TestClient.
- `[project.optional-dependencies].api` extra (`fastapi`, `uvicorn`,
  `python-multipart`, `httpx`).

### Changed
- Long-running operations (PDF extraction, NL ask, consolidator,
  apply-approved, inbox processing) now run as `BackgroundTasks` jobs
  with progress events streamed via Server-Sent Events.
- `{name}` and `{proposal_id}` path params are pattern-validated at the
  API boundary (defence-in-depth against path-traversal and glob-
  injection through downstream lookups).

### Moved
- `kgforge/ui/` → `legacy-streamlit/kgforge_ui/`. Still runnable via
  `pip install -e .[legacy]` + `streamlit run …` as a fallback.
- `[ui]` optional-dependency extra renamed to `[legacy]`.

### Removed
- "web UI" from the README's *Deliberately deferred* list (it now
  exists).

---

## 2026-05-08 — Caribbean Compliance Ontology prototype shipped

Single-statute prototype proved end-to-end on the Jamaica DPA 2020.
First real curator run on `dpa_2020_s6.pdf` succeeded: 14 entities
extracted by Claude Haiku, written to vault, branch
`proposals/dpa_2020_s6` committed, PDF archived.

### Added
- `schema/carib_compliance.ttl` — 5 classes, 5 properties, FIBO
  subClassOf alignments for `Statute` and `Regulator`.
- 8 hand-curated DPA 2020 vault entities (§1, §2 provision, §2 defs ×4,
  §5, §10).
- `scripts/{extractor,curator,to_turtle,load_to_oxigraph,ask,highlight,
  consolidate,apply_proposals,lint}.py` — CLI surface.
- `sparql/cq[1-3].rq` — three competency questions.
- `docs/demo_script.md` + outreach one-pager + email drafts for UWI
  researchers (Donalds, Barclay & Osei-Bryson).
- Mermaid architecture diagram + quickstart in the README.
