# Changelog

All notable changes to Callimachus are recorded here, newest first.
Format loosely follows [Keep a Changelog](https://keepachangelog.com);
the project does not yet follow strict semver — versions will land when
something visible to users or downstream packs changes.

---

## 2026-05-21 — Model-agnostic: LiteLLM + per-project model picker

Engine LLM calls now go through [LiteLLM](https://github.com/BerriAI/litellm),
so any provider with tool/function-calling support is usable: Anthropic,
OpenAI, Gemini, Mistral, Cohere, Together-hosted Llama, Bedrock, Azure
OpenAI, etc. The `anthropic` SDK is no longer a hard dependency.

### Added

- `callimachus/engine/llm.py` — thin provider-agnostic wrapper exposing
  `call_with_tool()` (forced function call → parsed dict) and
  `chat_text()` (plain completion). Bare `claude-*` / `gpt-*` / `gemini-*`
  model ids are auto-prefixed for back-compat with older packs.
- `PATCH /api/projects/{name}/pack/models` — writes new
  `models.extractor` / `models.ask` to the project's `pack.yaml`,
  validating the result before persisting and reverting on failure.
  Refuses to mutate built-in packs.
- `GET /api/settings` now returns a `providers` array (one entry per
  vendor with `env_var` + `configured` flag).
- Schema page **Models** section — Autocomplete picker per role with a
  curated dropdown plus free-form entry; live badge showing whether the
  selected model's provider key is present in the environment.
- Settings page **LLM provider keys** table — shows which providers the
  API process can see.
- `tests/api/test_smoke.py` assertions for the new settings shape and
  the built-in pack guard.

### Changed

- `pyproject.toml` dependencies: replaced `anthropic>=0.25.0` with
  `litellm==1.83.10` (exact pin — see below).
- Built-in and project packs (`compliance`, `thematic`, `densho_themes`)
  now use prefixed model ids (`anthropic/claude-haiku-4-5-20251001`,
  etc.) in their `pack.yaml`.
- `callimachus/engine/{extractor,consolidator,ask}.py` and
  `callimachus/api/routers/query.py` — all five LLM call sites refactored
  to use the new wrapper. No `import anthropic` left in engine code.

### Security

- `litellm` is pinned to an exact version (`==1.83.10`), not a range.
  This is deliberate hardening against the March 2026 PyPI supply-chain
  incident that shipped malicious `litellm` 1.82.7/1.82.8 releases —
  `1.83.0` was the clean re-release and `1.83.10` rolls up the April
  hardening pass. Bump deliberately after reviewing upstream release
  notes; never use `>=`.

### Verified

- Gemini smoke-tested end-to-end against `gemini/gemini-2.5-flash`:
  `chat_text`, forced `call_with_tool`, and a full
  `extractor.call_llm` against the compliance pack all return the
  expected shapes. Entities come back with `class`, `label`, `id`,
  `source_section`, `source_text` — the same fields the vault writer
  consumes from Anthropic output, no per-provider branching needed.
- Smoke harness lives at `scripts/_smoke_gemini.py` (underscore-prefixed
  so it doesn't appear in the CLI entry points). Reusable for
  smoke-testing other providers — change `MODEL` at the top.

### Hardened

- `engine/llm.py` now tolerates empty `response.choices` from any
  provider (Gemini occasionally returns this under safety filtering or
  capacity pressure). `call_with_tool` returns an empty
  `ToolCallResult` with `finish_reason="no_choices"` instead of an
  `IndexError`; `chat_text` returns `""`.

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
