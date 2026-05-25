# Vault Browser & Graph Viewer — Implementation Plan

**Drafted:** 2026-05-26
**Status:** Planned, not started

## Why

The vault — the per-entity Markdown files Callimachus extracts from each
document — is the canonical artifact of the system. It's what reviewers
inspect, what graphs are built from, and what makes the "human-in-the-loop"
story concrete. Today it's only visible via:

- The Pending Review page (only shows *unapproved* submissions)
- The Proposals page (only shows *consolidator output*, not raw entities)
- External tooling like Obsidian pointed at `vault/`

That last option works, but it puts a critical value prop behind a separate
install and a manual path setup. Two strangers on a demo call won't both
have Obsidian configured the same way. The "see what the system extracted
from your documents" experience needs to live inside the app.

This document plans the work in two phases. Phase 1 delivers the read-only
document/entity browser; Phase 2 adds the visual graph view on top.

## What's already in place

A useful amount of the backend already exists:

- **`callimachus/api/vault_view.py`** — frontmatter parsing, doc-id matching,
  packaging a Markdown file as an `EntityCardOut`. Used today by the
  pending-submissions router.
- **`EntityCardOut`** — API response model with `class`, `label`,
  `source_section`, `source_page`, `source_text`, `properties`.
- **`GraphResultOut`** in `callimachus/api/models/query.py` — SPARQL graph
  results as a list of stringified triples.
- **`ProposalMiniGraph.tsx`** — already renders DOT strings as SVG via
  `@viz-js/viz` (Graphviz WASM). The renderer is reusable; what's missing is
  feeding it vault-wide graph data.
- **Built-in competency questions** — every pack ships pre-defined
  "interesting subgraph" SPARQL queries, perfect seeds for graph slices.

What's missing is purely UI surface area: no page that browses the
*approved* vault, no full-graph visualization, no entity-detail view
outside the review flows.

## Phase 1 — Document & Entity Browser (read-only)

Mirrors what Obsidian provides today, minus the external dependency.

### UX

A new `VaultPage.tsx` with a three-pane layout:

| Pane | Content |
|---|---|
| Left | List of source documents in this project. Derived from the vault by grouping entity files by their `source_document` frontmatter field (or filename prefix as a fallback — same precedence as `vault_view.vault_files_for`). |
| Middle | The entities extracted from the selected document, rendered as cards using the existing `EntityCardOut` shape. Class, label, source section, page. |
| Right | Full content of the selected entity: frontmatter as a properties table, body as rendered Markdown (using the existing `react-markdown` setup). |

Optional: a "show source" affordance that displays the `source_text` excerpt
inline, with `source_page` as a citation. The PDF itself doesn't need to be
embedded — the excerpt is what reviewers actually read.

### API work

Two new endpoints, both ~30 lines on top of existing helpers:

```
GET  /projects/{name}/vault
     → { documents: [{ doc_id, source_document, entity_count, classes: [...] }] }

GET  /projects/{name}/vault/{filename}
     → { filename, frontmatter, body }   # full markdown content
```

A doc-grouped variant of `vault_files_for` belongs in `vault_view.py`. The
single-file endpoint is essentially `Path.read_text()` plus the frontmatter
splitter that's already there.

### Frontend work

- One new route under `frontend/src/routes/VaultPage.tsx`.
- Add the route to `RootShell`'s nav.
- Three new TanStack Query hooks in `frontend/src/api/hooks.ts`.
- No new dependencies.

### Constraints

- **Read-only.** No editing Markdown in the UI. The "nothing lands in the
  vault unattended" rule from the README applies to this view too. Any
  vault edit goes through the Proposals flow.
- **Approved vault only.** The pending and proposals pages handle the
  pre-approval states. This page is for browsing what's been accepted into
  the canonical graph.

### Estimate

A focused afternoon. Most of the backend already exists.

## Phase 2 — Graph Viewer

Renders the actual vault graph visually, click-through to Phase 1.

### UX

A new `GraphPage.tsx`:

- Default view shows a structural projection of the vault: classes as node
  types, `rdfs:label` (or the pack's label property) as node labels, every
  relation property as an edge.
- Click a node → opens the entity in the Phase 1 document browser.
- Filter controls: by class, by document of origin, by approval state.
- A "show results from CQ X" mode that scopes the graph to the rows returned
  by one of the pack's competency questions. CQs are already the
  pack-author's curated "interesting subgraph" definitions, so this is the
  fastest way to give users meaningful starting views.

### API work

One new endpoint, two ways to invoke it:

```
GET  /projects/{name}/graph                  → full vault as DOT
GET  /projects/{name}/graph?cq={cq_id}        → DOT scoped to CQ results
```

The transform is "triples → DOT," which is a ~50-line server-side function
(or pushable to the client if the triples are returned as-is via the
existing `GraphResultOut`). Server-side is probably better because it
centralizes the styling choices (node shape per class, edge labels).

### Frontend work

- One new route `frontend/src/routes/GraphPage.tsx`.
- Factor `ProposalMiniGraph.tsx` into a reusable `<GraphvizSvg dot={...}>`
  component (or reuse it directly — its current API already accepts an
  arbitrary DOT string).
- Click handlers on SVG nodes that route to `/projects/{name}/vault?file={…}`.
- Filter UI for class/document/CQ selection.

### The scaling question

Graphviz WASM will happily render a 500-node graph, but it'll be a hairball
that no one wants to look at. Two ways to keep this useful:

1. **Default to a slice.** The full-vault view is "show me one document's
   contribution to the graph" or "show me everything of class X." Make the
   user opt in to "show everything."
2. **CQ-driven views.** Each pack already has 5–10 CQs that represent the
   questions the schema was designed to answer. Default the graph page to a
   CQ picker; the result graph for any single CQ is small enough to render
   meaningfully.

If users actually outgrow Graphviz, the next step is a layout-aware library
(cytoscape.js or react-flow). Don't add it speculatively — Graphviz is
already a dep and already works.

### Constraints

- **No pan/zoom in v1.** Graphviz produces a static SVG. CSS scroll is
  enough. Add interactive pan/zoom only if users actually ask for it.
- **No graph-editing UI.** Same rule as Phase 1. Graph mutations happen via
  Proposals, not by dragging nodes around.

### Estimate

Probably a long day, mostly UI. The transform to DOT and the click-through
plumbing are the substantive parts; everything else is layout and styling.

## What this plan deliberately doesn't include

A few things worth naming explicitly so they don't sneak into scope:

- **Editing the vault from the UI.** Out of scope. Breaks the audit story.
- **Inline PDF rendering.** Out of scope for v1. The `source_text` excerpt
  with a page citation is sufficient for reviewers. PDF embedding is a heavy
  dependency (pdf.js) for marginal value.
- **Real-time collaboration / multi-user state.** Out of scope. Callimachus
  is currently a single-reviewer tool; multi-user is a separate project.
- **Replacing the existing Query page.** The Query page is for SPARQL and NL
  ask. The Graph page is visualization. Both serve different workflows and
  should stay separate.

## Suggested sequencing

1. **Phase 1 first.** It delivers most of the value alone (no more Obsidian
   dependency), and the entity-detail view it builds is also what the Phase
   2 click-through targets land on. Building Phase 2 first would mean
   shipping a graph view whose nodes link nowhere useful.
2. **Phase 2 second**, scoped to CQ-driven views before full-vault rendering.
3. **Defer everything else** (pan/zoom, alternate graph libs, PDF embed)
   until a real user asks for it.
