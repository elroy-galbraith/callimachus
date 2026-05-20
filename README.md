# Caribbean Compliance Ontology — Prototype

A minimal end-to-end demonstration of the **curator-agent methodology** for
converting Caribbean statutory text into structured, queryable RDF.

**Primary statute:** Jamaica Data Protection Act 2020 (DPA 2020)  
**Differentiating idea:** PR-as-ontology-mutation — every proposed ontology
change arrives as a reviewable git branch that a human can inspect, debate,
and merge (or reject).

> This work is complementary to Donalds, Barclay & Osei-Bryson (2023)
> *Towards a Cybercrime Classification Ontology for Developing Countries*.
> That work covers cybercrime classification; this prototype covers
> privacy-compliance obligations. Alignment between the two artifacts is a
> planned Phase 2 activity.

---

## Quickstart (≤ 5 minutes)

```bash
# 1. Clone and install
git clone https://github.com/elroy-galbraith/carib-comp-ont.git
cd carib-comp-ont
pip install -r requirements.txt

# 2. Generate Turtle from the hand-curated seed
python scripts/to_turtle.py
# → writes vault/vault.ttl

# 3. Load into Oxigraph and run the three competency queries
python scripts/load_to_oxigraph.py
# → answers CQ1 (obligations), CQ2 (regulators), CQ3 (definitions)

# 4. Drop a DPA PDF into inbox/ and watch the curator loop
python scripts/curator.py --once
# → runs extractor, opens proposals/<doc-id> branch, commits new vault files

# 5. Review the proposed PR
git log proposals/<doc-id>
git diff main...proposals/<doc-id>
git checkout main && git merge proposals/<doc-id>

# 6. Ask a natural-language question over the merged graph
python scripts/ask.py "What does the DPA 2020 say about biometric data?" --show-sparql
# → Claude writes SPARQL, Oxigraph executes, Claude summarises with citations
```

---

## Web UI (React + FastAPI)

For interactive use there's a React + FastAPI app under
[kgforge/api/](kgforge/api/) and [frontend/](frontend/). The CLI flow
above stays canonical for scripting and demos; the web app is the
day-to-day interface.

**Backend** (FastAPI wrapping `kgforge.engine` + `kgforge.project`):

```powershell
pip install -e .[api]
uvicorn kgforge.api.main:app --reload --port 8000
# → OpenAPI spec at http://localhost:8000/openapi.json
# → API root   at http://localhost:8000/api/projects
```

**Frontend** (Vite + React + TypeScript + Mantine):

```powershell
cd frontend
npm install
npm run dev          # vite at :5173, proxies /api/* to :8000
# or, with both at once (from the frontend dir):
npm run dev:all
```

The Vite dev server proxies `/api/*` to the FastAPI process, so the
browser sees same-origin and no CORS dance is needed.

Seven pages have full parity with the original Streamlit app: **Projects**,
**Dashboard**, **Schema**, **Query**, **Proposals**, **Settings**, and
**Help**. Long-running operations (PDF extraction, NL ask, consolidator,
apply-approved) run as background jobs and stream progress events via
Server-Sent Events.

```powershell
# Run the smoke tests
pytest tests/api -q
```

The original Streamlit UI is archived under [legacy-streamlit/](legacy-streamlit/);
see [legacy-streamlit/README.md](legacy-streamlit/README.md) for how to run
it as a reference / fallback.

---

## Architecture

```mermaid
flowchart LR
    subgraph inbox["📥 inbox/"]
        PDF[statute.pdf]
    end

    subgraph scripts["scripts/"]
        curator["curator.py\n(watchdog)"]
        extractor["extractor.py\n(Docling → Haiku)"]
        to_turtle["to_turtle.py"]
        load["load_to_oxigraph.py"]
        ask["ask.py\n(NL → SPARQL → answer)"]
    end

    subgraph vault["📂 vault/"]
        MD["entity_*.md\n(Markdown + YAML)"]
        TTL["vault.ttl"]
    end

    subgraph git["🌿 git"]
        main["main branch"]
        proposals["proposals/<doc-id>"]
    end

    subgraph store["🔷 Oxigraph (in-memory)"]
        schema["schema/carib_compliance.ttl"]
        triples["vault triples"]
        sparql["SPARQL queries"]
    end

    PDF -->|"file event"| curator
    curator -->|"subprocess"| extractor
    extractor -->|"Docling\ntext"| haiku["☁️ Claude Haiku\n(JSON Schema tool use)"]
    haiku -->|"entities JSON"| extractor
    extractor -->|"writes"| MD
    curator -->|"git checkout -b\ngit commit"| proposals
    proposals -->|"human review\ngit merge"| main
    main --> to_turtle
    to_turtle -->|"generates"| TTL
    TTL --> load
    schema --> load
    load --> triples
    triples --> sparql
    triples --> ask
    schema --> ask
    ask -->|"NL question"| sonnet["☁️ Claude Sonnet\n(SPARQL synthesis + summary)"]
    sonnet -->|"SPARQL"| ask
```

---

## Repository layout

```
carib-comp-ont/
├── schema/
│   └── carib_compliance.ttl   # OWL schema: 5 classes, 5 properties, FIBO subclass
├── vault/
│   ├── dpa2020.md             # Statute — Data Protection Act 2020
│   ├── dpa2020_s2.md          # Provision — §2 Interpretation
│   ├── dpa2020_s2_*.md        # Definitions from §2 (×4)
│   ├── dpa2020_ico.md         # Regulator — Information Commissioner
│   ├── dpa2020_obligation_*.md# Obligations
│   └── vault.ttl              # Generated — do not edit manually
├── scripts/
│   ├── extractor.py           # PDF → Docling → Haiku → Markdown+YAML
│   ├── curator.py             # inbox watcher → extractor → git PR
│   ├── to_turtle.py           # vault/*.md → Turtle triples
│   ├── load_to_oxigraph.py    # Turtle → Oxigraph → SPARQL
│   └── ask.py                 # NL question → Sonnet SPARQL → answer
├── sparql/
│   ├── cq1_obligations_on_controller.rq
│   ├── cq2_regulators.rq
│   └── cq3_definitions.rq
├── inbox/                     # Drop PDFs here for the curator to process
│   └── processed/             # PDFs move here after extraction
├── docs/
│   ├── demo_script.md
│   └── outreach/
│       ├── one_pager.md
│       └── email_draft.md
├── HELD_OUT.md                # Evaluation corpus quarantine policy
├── requirements.txt
└── README.md
```

---

## Schema overview

| Class | FIBO alignment | Description |
|---|---|---|
| `cco:Statute` | `fibo-fbc-fct-rga:Regulation` | Enacted primary legislation |
| `cco:Provision` | — | Numbered section or subsection |
| `cco:Definition` | subclass of Provision | Term formally defined within a provision |
| `cco:Regulator` | `fibo-be-ge-ge:GovernmentalAuthority` | Enforcement body |
| `cco:Obligation` | — | Duty imposed on a specified party |

| Property | Domain | Range | Description |
|---|---|---|---|
| `cco:definedIn` | Definition | Provision | Where a term is defined |
| `cco:enforcedBy` | Statute | Regulator | Enforcement relationship |
| `cco:imposesObligationOn` | Obligation | (entity) | Obligation bearer |
| `cco:applicableTo` | Provision | (entity) | Governing scope |
| `cco:relatedTo` | Thing | Thing | General association |

---

## Hand-curated seed (DPA 2020 §1–§10)

Eight entities manually extracted to validate the data shape before automation:

| Entity | Class | Source |
|---|---|---|
| Data Protection Act 2020 | Statute | §1 |
| DPA 2020 §2 — Interpretation | Provision | §2 |
| Personal Data | Definition | §2 |
| Data Subject | Definition | §2 |
| Data Controller | Definition | §2 |
| Data Processor | Definition | §2 |
| Information Commissioner | Regulator | §5 |
| Obligation to Process Lawfully | Obligation | §10 |

---

## Competency questions

| # | Question | Query file |
|---|---|---|
| CQ1 | List every obligation imposed on a DataController by the DPA | `sparql/cq1_obligations_on_controller.rq` |
| CQ2 | Which regulators enforce the DPA 2020? | `sparql/cq2_regulators.rq` |
| CQ3 | What terms are formally defined in the DPA 2020? | `sparql/cq3_definitions.rq` |

---

## Natural-language QA

Pre-written competency questions cover the foreseen queries. For ad-hoc
questions, `scripts/ask.py` runs a three-step agent loop over the same graph:

1. **Synthesise** — Claude Sonnet receives the schema, the live entity
   catalog, and the existing CQs as few-shot, and emits one SPARQL query via
   tool-use.
2. **Execute** — the query runs against `schema/carib_compliance.ttl` +
   `vault/vault.ttl` in pyoxigraph.
3. **Summarise** — Claude turns the result rows into plain prose with
   `[Label](vault/<entity>.md)` citations back to the reviewable Markdown.

```bash
python scripts/ask.py "Which obligations apply to a data controller?"
python scripts/ask.py "What does the DPA 2020 say about biometric data?" --show-sparql
python scripts/ask.py "List every defined term" --build-vault
```

`--show-sparql` prints the generated query and the raw result table — useful
for the demo and for spotting when the model picked a brittle IRI match
instead of a generalisable label-based one.

---

## Demo script

See [docs/demo_script.md](docs/demo_script.md) for the two-minute walk-through.

---

## Extending the ontology

**Add a new jurisdiction** — drop the statute PDF into `inbox/`, run
`python scripts/curator.py --once`, review the proposed branch, and merge.
The curator adds new vault files but never edits existing ones; conflicts stay
human-resolvable.

**Add a new class or property** — edit `schema/carib_compliance.ttl` directly.
Keep FIBO alignment where a matching concept exists; add a comment citing the
source section if you introduce a new term. Re-run `to_turtle.py` and
`load_to_oxigraph.py` to verify the graph still answers all three CQs.

**Add a competency question** — write a `.rq` file in `sparql/` and add a row
to the CQ table above. A passing CQ is the acceptance criterion for any schema
change.

---

## Scope

**In scope (prototype):** DPA 2020 §1–§10, FIBO alignment for Regulator and
Statute, single-shot Haiku extractor, minimal git-PR curator loop, Oxigraph
SPARQL, NL → SPARQL QA agent (Sonnet), CLI-only.

**Deliberately deferred:** Cybercrimes Act 2015, BOJ circulars, SHACL shapes,
OWL 2 RL reasoning, Sonnet escalation, gold-standard annotation.

---

## Acknowledgements

This prototype is informed by and complementary to:

> Donalds, C., Barclay, C., & Osei-Bryson, K.-M. (2023).
> *Towards a Cybercrime Classification Ontology for Developing Countries.*

The cybercrime and privacy-compliance domains intersect at incident-response
obligations and data-breach definitions. Alignment between these ontologies
is a planned Phase 2 activity; we welcome feedback from the original authors.

---

## See also

- [docs/outreach/one_pager.md](docs/outreach/one_pager.md) — one-page project summary for outreach and paper submissions
- [HELD_OUT.md](HELD_OUT.md) — evaluation corpus quarantine policy (M0)

---

## License

MIT © 2026 Elroy Galbraith
