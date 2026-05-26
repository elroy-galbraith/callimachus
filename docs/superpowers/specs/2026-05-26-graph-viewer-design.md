# Graph Viewer — Design Spec

**Date:** 2026-05-26
**Status:** Approved, ready for implementation
**Context:** Phase 2 of `docs/plan_vault_browser.md`. Phase 1 (vault browser) is complete.

## What we're building

A dedicated **Graph page** in the Callimachus nav that renders the vault as a visual graph. The user selects a competency question (CQ); the graph renders the subgraph of entities relevant to that question. Clicking a node opens an entity detail drawer. No editing, no pan/zoom, no PDF embed — read-only visualization of the approved vault.

## Design decisions

| Question | Decision | Reason |
|---|---|---|
| Where does it live? | Separate top-level nav page ("Graph") | Keeps vault browser uncluttered; graph + filters + drawer need horizontal space |
| Default starting state | CQ picker — no graph until a CQ is selected | Pack CQs are curated "interesting subgraphs"; guarantees legible first render |
| Node click behaviour | Side drawer on the Graph page | Keeps graph visible for continued exploration; "View in Vault" link available for full detail |

## Architecture & data flow

1. User opens Graph page → CQ list rendered from `useProjectPack` (no extra fetch)
2. User selects a CQ → `GET /projects/{name}/graph?cq={cq_id}` called
3. Backend: run CQ SPARQL (SELECT) → collect entity URIs from result rows → CONSTRUCT subgraph → transform triples to DOT string → return `{ dot: "..." }`
4. Frontend: feed DOT to Graphviz WASM renderer (`@viz-js/viz`, already a dep)
5. User clicks SVG node → node ID decodes to vault filename → `useVaultFile` fetch → Mantine Drawer with `PropertiesTable` + "View in Vault" link

Nothing in the engine layer is touched. New code lives entirely in the API layer and frontend.

## Backend

### New file: `callimachus/api/routers/graph.py`

```
GET /projects/{name}/graph?cq={cq_id}   → GraphDotOut
```

Handler steps:
1. `resolve_cq_sparql(project, cq_id)` — existing helper, raises `KeyError` → 404 if unknown
2. `ensure_vault_ttl(project)` — existing helper, raises `FileNotFoundError` → 404
3. `cache.get(project)` — get the pyoxigraph store
4. `ask_engine.run_sparql(store, cq_sparql)` — run CQ as SELECT
5. Collect all URI-shaped values from result rows
6. Run CONSTRUCT: `CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o . FILTER(?s IN (<uri>, ...)) }`
7. `triples_to_dot(triples, project.pack)` — new function in `vault_view.py`
8. Return `GraphDotOut(dot=dot_string)`

### New function: `vault_view.triples_to_dot(triples, pack, vault_files)`

Transforms a list of stringified triples into a Graphviz DOT string. `vault_files` is the list of vault `Path` objects (from `vault_files_for(project)`) used to build a URI-local-name → filename map for DOT node IDs.

- **Node label** — `rdfs:label` value if present in the triples, else local name of the subject URI
- **Node color/shape** — grouped by `rdf:type`; one color per class drawn from the pack's class list; `rdf:type` edges are not rendered as graph edges (already encoded in node appearance)
- **Edge label** — local name of the predicate
- **Node ID in DOT** — the vault filename of the entity (e.g. `personal_data.md`), URL-encoded so it's safe as a DOT identifier. `triples_to_dot` receives the vault file listing (from `vault_files_for(project)`) to build a URI → filename map. The click handler reads the SVG `<g id="...">` attribute and decodes it directly to get the filename for `useVaultFile`.

### New model: `callimachus/api/models/graph.py`

```python
class GraphDotOut(BaseModel):
    dot: str
```

Register in `callimachus/api/models/__init__.py` and mount the router in `callimachus/api/main.py`.

## Frontend

### Refactor: extract `PropertiesTable`

Move `PropertiesTable` and `PropertyValue` from `frontend/src/routes/VaultPage.tsx` to `frontend/src/components/PropertiesTable.tsx`. `VaultPage.tsx` imports from there; the new drawer also imports from there. No behaviour change.

### New component: `frontend/src/components/GraphvizSvg.tsx`

```tsx
<GraphvizSvg dot={string} onNodeClick={(nodeId: string) => void} />
```

- Factors the WASM loading + `renderSVGElement` logic out of `ProposalMiniGraph.tsx`
- After render, attaches `click` listeners to each `<g>` element in the SVG; reads the `id` attribute as the node ID
- `ProposalMiniGraph.tsx` becomes a thin wrapper: `<GraphvizSvg dot={dot} />`

### New hook: `useVaultGraph`

```ts
// in frontend/src/api/hooks.ts
useVaultGraph(name: string | undefined, cqId: string | undefined)
// queryKey: [name, "graph", cqId]
// GET /projects/{name}/graph?cq={cqId}
// enabled when both defined
```

Add `vaultGraph` to the `qk` query key map.

### New route: `frontend/src/routes/GraphPage.tsx`

Structure:

```
<Stack>
  <Title>Graph</Title>

  <CqPicker>                  ← buttons, one per CQ from useProjectPack
    Selected CQ highlighted
  </CqPicker>

  {selectedCqId && (
    <GraphvizSvg              ← fills available width
      dot={graphData.dot}
      onNodeClick={openDrawer}
    />
  )}

  <Drawer position="right">   ← Mantine Drawer, opened by onNodeClick
    <PropertiesTable frontmatter={...} />
    source_text blockquote
    <Button>View in Vault →</Button>
  </Drawer>
</Stack>
```

States to handle:
- No CQ selected → instructional text "Select a question above to render its subgraph"
- Loading → `<Loader>`
- Error (404 / no TTL) → Alert with "Rebuild TTL" button (same pattern as Query page)
- Empty result (no entities matched CQ) → "No entities matched this question"
- Drawer loading (vault file fetch) → skeleton or loader inside drawer

### Nav

Add "Graph" entry to `RootShell`'s sidebar nav, between Vault and Query. Use `IconShare2` or `IconNetwork` from `@tabler/icons-react`.

### Route registration

Add `<Route path="graph" element={<GraphPage />} />` inside the project shell route in `App.tsx`.

## Edge cases

| Case | Behaviour |
|---|---|
| Vault TTL not built | 404 from endpoint → frontend shows Alert + "Rebuild TTL" button |
| CQ is already a CONSTRUCT query | URIs collected from `triples` list instead of `rows`; handler detects `kind == "graph"` and adjusts collection logic |
| CQ returns no entities | Empty CONSTRUCT result → empty DOT → frontend shows empty-state message, not blank SVG |
| Vault filename contains slashes/dots | DOT node `id` is the URL-encoded filename; click handler decodes it directly — no secondary lookup needed |
| `PropertiesTable` drawer fetch fails | Error state inside drawer; graph remains interactive |

## What this spec does not include

- Pan/zoom (defer until a user asks)
- `?doc=` / `?cls=` filter params (wired in v1 as disabled controls; backend params added in a follow-up)
- Graph editing (out of scope — vault mutations go through Proposals)
- Full-vault render (opt-in "Show all" button deferred to follow-up)
- PDF embed

## File checklist

Backend (new/modified):
- `callimachus/api/routers/graph.py` — new
- `callimachus/api/models/graph.py` — new
- `callimachus/api/models/__init__.py` — add `GraphDotOut`
- `callimachus/api/main.py` — mount graph router
- `callimachus/api/vault_view.py` — add `triples_to_dot`

Frontend (new/modified):
- `frontend/src/components/GraphvizSvg.tsx` — new (factored from ProposalMiniGraph)
- `frontend/src/components/PropertiesTable.tsx` — new (extracted from VaultPage)
- `frontend/src/components/ProposalMiniGraph.tsx` — thin wrapper, simplified
- `frontend/src/routes/GraphPage.tsx` — new
- `frontend/src/routes/VaultPage.tsx` — import PropertiesTable from components/
- `frontend/src/api/hooks.ts` — add `useVaultGraph`, `qk.vaultGraph`
- `frontend/src/api/types.ts` — add `GraphDotOut`
- `frontend/src/components/RootShell.tsx` — add Graph nav entry
- `frontend/src/App.tsx` — register graph route
