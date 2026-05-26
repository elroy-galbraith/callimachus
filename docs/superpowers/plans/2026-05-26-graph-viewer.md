# Graph Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Graph page to the Callimachus nav that visualises the approved vault as a Graphviz DOT graph scoped to a competency question, with an entity-detail side drawer on node click.

**Architecture:** A new `GET /projects/{name}/graph?cq={cq_id}` endpoint runs the named CQ as a SELECT, collects entity IRIs from the result rows, runs a CONSTRUCT to fetch those entities' immediate triples, and transforms them to a DOT string server-side. The React frontend renders the DOT via the existing `@viz-js/viz` WASM renderer (already a dep); clicking a `<g class="node">` in the SVG opens a Mantine `Drawer` that fetches and displays the entity's vault file using the existing `useVaultFile` hook.

**Tech Stack:** Python/FastAPI (backend), React 18 + TypeScript + Mantine v7 + TanStack Query + `@viz-js/viz` WASM (frontend), pytest + FastAPI TestClient (tests)

**Spec:** `docs/superpowers/specs/2026-05-26-graph-viewer-design.md`

---

## File map

| File | Action | Purpose |
|---|---|---|
| `callimachus/api/vault_view.py` | modify | add `triples_to_dot`, `all_vault_files` |
| `callimachus/api/models/graph.py` | create | `GraphDotOut` response model |
| `callimachus/api/models/__init__.py` | modify | export `GraphDotOut` |
| `callimachus/api/routers/graph.py` | create | `GET /projects/{name}/graph` handler |
| `callimachus/api/main.py` | modify | mount graph router |
| `tests/api/test_graph.py` | create | unit + HTTP smoke tests |
| `frontend/src/components/PropertiesTable.tsx` | create | extracted from VaultPage |
| `frontend/src/components/GraphvizSvg.tsx` | create | extracted from ProposalMiniGraph, adds `onNodeClick` |
| `frontend/src/components/ProposalMiniGraph.tsx` | modify | thin wrapper around GraphvizSvg |
| `frontend/src/routes/VaultPage.tsx` | modify | import PropertiesTable from components/ |
| `frontend/src/routes/GraphPage.tsx` | create | CQ picker + graph + entity drawer |
| `frontend/src/api/types.ts` | modify | add `GraphDotOut` |
| `frontend/src/api/hooks.ts` | modify | add `useVaultGraph` |
| `frontend/src/components/ProjectShell.tsx` | modify | add Graph nav entry |
| `frontend/src/App.tsx` | modify | register graph route |

---

### Task 1: `triples_to_dot` and `all_vault_files` in `vault_view.py`

**Files:**
- Modify: `callimachus/api/vault_view.py`
- Create: `tests/api/test_graph.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_graph.py`:

```python
"""Tests for triples_to_dot and the /graph HTTP endpoint."""
from __future__ import annotations

from pathlib import Path

import pytest

from callimachus.api.vault_view import all_vault_files, triples_to_dot


# ---------- triples_to_dot unit tests ----------------------------------------

def test_triples_to_dot_empty_returns_valid_digraph() -> None:
    dot = triples_to_dot([], pack_classes=[], vault_files=[])
    assert dot.startswith("digraph vault {")
    assert dot.endswith("}")


def test_triples_to_dot_rdf_type_sets_node_color() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=["Obligation"], vault_files=[])
    assert "#4c6ef5" in dot  # first palette color assigned to first class


def test_triples_to_dot_rdfs_label_used_as_display_label() -> None:
    triples = [
        '<http://ex.org/PersonalData> <http://www.w3.org/2000/01/rdf-schema#label>'
        ' "Personal Data" .',
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "Personal Data" in dot


def test_triples_to_dot_non_type_predicate_becomes_edge() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://ex.org/pack#hasController>"
        " <http://ex.org/Controller> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    assert "->" in dot
    assert "hasController" in dot


def test_triples_to_dot_rdf_type_not_rendered_as_edge() -> None:
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[])
    # rdf:type is encoded as node colour, NOT as an arrow
    assert "->" not in dot


def test_triples_to_dot_vault_filename_as_node_id(tmp_path: Path) -> None:
    vault_file = tmp_path / "personal_data_e0.md"
    vault_file.write_text("---\nclass: Obligation\n---\n", encoding="utf-8")
    triples = [
        "<http://ex.org/PersonalData> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
        " <http://ex.org/pack#Obligation> .",
    ]
    dot = triples_to_dot(triples, pack_classes=[], vault_files=[vault_file])
    # The node ID is the URL-encoded vault filename
    assert "personal_data_e0.md" in dot


def test_all_vault_files_returns_md_files(tmp_path: Path, monkeypatch) -> None:
    import callimachus.api.deps as api_deps
    import callimachus.project.project as pm
    from callimachus.project import create_from_template

    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(pm, "projects_dir", lambda: projects_root)
    api_deps.clear_project_cache()
    project = create_from_template("avf_test", template="thematic", backend="filesystem")
    project.vault_dir.mkdir(parents=True, exist_ok=True)
    (project.vault_dir / "alpha_e0.md").write_text("---\n---\n", encoding="utf-8")
    (project.vault_dir / "beta_e0.md").write_text("---\n---\n", encoding="utf-8")

    files = all_vault_files(project)
    assert len(files) == 2
    assert all(f.suffix == ".md" for f in files)
    api_deps.clear_project_cache()
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\python -m pytest tests/api/test_graph.py -v -k "triples_to_dot or all_vault_files" 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'triples_to_dot' from 'callimachus.api.vault_view'`

- [ ] **Step 3: Add imports and constants to `callimachus/api/vault_view.py`**

Add after the existing imports (note: `re` is already imported — do not add it again):

```python
from urllib.parse import quote as _url_quote
```

Add after the existing `_ENTITY_SUFFIX_RE` constant:

```python
_IRI_IN_TRIPLE_RE = re.compile(r"<([^>]+)>")
_LITERAL_IN_TRIPLE_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_NORMALIZE_RE = re.compile(r"[\s\-_]")

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"

_CLASS_COLORS = [
    "#4c6ef5", "#f76707", "#2f9e44", "#e03131",
    "#1098ad", "#d6336c", "#7048e8", "#f08c00",
]
```

- [ ] **Step 4: Add `_normalize_for_lookup`, `_local_name`, `all_vault_files`, and `triples_to_dot` to the end of `callimachus/api/vault_view.py`**

Append after `read_vault_file`:

```python
def _normalize_for_lookup(s: str) -> str:
    """Lowercase and strip spaces/hyphens/underscores for URI→filename matching."""
    return _NORMALIZE_RE.sub("", s).lower()


def _local_name(iri: str) -> str:
    """Extract the local name from an IRI (after the last # or /)."""
    return iri.rsplit("#", 1)[-1] if "#" in iri else iri.rsplit("/", 1)[-1]


def all_vault_files(project: Project) -> list[Path]:
    """All approved vault markdown files (top-level only; proposals subdir excluded)."""
    if not project.vault_dir.exists():
        return []
    return sorted(project.vault_dir.glob("*.md"))


def triples_to_dot(
    triples: list[str],
    pack_classes: list[str],
    vault_files: list[Path],
) -> str:
    """Convert stringified RDF triples to a Graphviz DOT string.

    DOT node IDs are URL-encoded vault filenames so the browser click
    handler can call ``decodeURIComponent`` on the SVG ``<title>`` element
    and pass the result straight to ``GET /vault/files/{filename}``.
    """
    # Build normalized-local-name → vault-filename lookup.
    # Strategy: strip the _e<digits> suffix, then normalize (lowercase +
    # strip separators) and compare with the URI local name treated the
    # same way. Falls back to frontmatter label if no stem match.
    local_to_file: dict[str, str] = {}
    for path in vault_files:
        stem = _ENTITY_SUFFIX_RE.sub("", path.stem)
        local_to_file[_normalize_for_lookup(stem)] = path.name
        meta = read_frontmatter(path)
        label_val = meta.get("label")
        if isinstance(label_val, str) and label_val.strip():
            local_to_file[_normalize_for_lookup(label_val.strip())] = path.name

    class_colors: dict[str, str] = {
        cls: _CLASS_COLORS[i % len(_CLASS_COLORS)]
        for i, cls in enumerate(pack_classes)
    }

    node_labels: dict[str, str] = {}  # iri → display label
    node_types: dict[str, str] = {}   # iri → class name
    edges: list[tuple[str, str, str]] = []  # (subj_iri, pred_local, obj_iri)

    for triple_str in triples:
        iris = _IRI_IN_TRIPLE_RE.findall(triple_str)
        if len(iris) < 2:
            continue
        subj_iri, pred_iri = iris[0], iris[1]
        if pred_iri == _RDF_TYPE and len(iris) >= 3:
            node_types[subj_iri] = _local_name(iris[2])
        elif pred_iri == _RDFS_LABEL:
            m = _LITERAL_IN_TRIPLE_RE.search(triple_str)
            if m:
                node_labels[subj_iri] = m.group(1)
        elif len(iris) >= 3:
            edges.append((subj_iri, _local_name(pred_iri), iris[2]))

    all_iris = (
        set(node_labels)
        | set(node_types)
        | {s for s, _, _ in edges}
        | {o for _, _, o in edges}
    )

    def _node_id(iri: str) -> str:
        local = _local_name(iri)
        filename = local_to_file.get(_normalize_for_lookup(local), f"{local}.md")
        return _url_quote(filename, safe="")

    lines = [
        "digraph vault {",
        "  rankdir=LR;",
        '  node [shape=box style=filled fontsize=11 fontname="Helvetica"];',
    ]
    for iri in sorted(all_iris):
        label = node_labels.get(iri, _local_name(iri))
        cls = node_types.get(iri, "")
        color = class_colors.get(cls, "#e9ecef")
        nid = _node_id(iri)
        safe_label = label.replace('"', "'")
        lines.append(
            f'  "{nid}" [label="{safe_label}" fillcolor="{color}" tooltip="{nid}"];'
        )
    for subj, pred_local, obj in edges:
        sid = _node_id(subj)
        oid = _node_id(obj)
        safe_pred = pred_local.replace('"', "'")
        lines.append(f'  "{sid}" -> "{oid}" [label="{safe_pred}"];')
    lines.append("}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run unit tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/api/test_graph.py -v -k "triples_to_dot or all_vault_files"
```

Expected: all 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add callimachus/api/vault_view.py tests/api/test_graph.py
git commit -m "feat(api): triples_to_dot + all_vault_files helpers"
```

---

### Task 2: Graph model, router, and HTTP endpoint

**Files:**
- Create: `callimachus/api/models/graph.py`
- Modify: `callimachus/api/models/__init__.py`
- Create: `callimachus/api/routers/graph.py`
- Modify: `callimachus/api/main.py`
- Extend: `tests/api/test_graph.py`

- [ ] **Step 1: Write the failing HTTP endpoint tests**

Append to `tests/api/test_graph.py`:

```python
# ---------- HTTP endpoint tests -----------------------------------------------

from fastapi.testclient import TestClient

from callimachus.api.main import create_app


@pytest.fixture(scope="module")
def graph_client():
    with TestClient(create_app()) as c:
        r = c.post("/api/projects/compliance/query/rebuild-ttl")
        assert r.status_code == 200, r.text
        yield c


def test_graph_returns_dot_for_valid_cq(graph_client: TestClient) -> None:
    r = graph_client.get("/api/projects/compliance/graph?cq=cq1")
    assert r.status_code == 200
    body = r.json()
    assert "dot" in body
    assert "digraph" in body["dot"]


def test_graph_404_for_unknown_cq(graph_client: TestClient) -> None:
    r = graph_client.get("/api/projects/compliance/graph?cq=nope")
    assert r.status_code == 404


def test_graph_404_when_vault_missing(tmp_path: Path, monkeypatch) -> None:
    import callimachus.api.deps as api_deps
    import callimachus.project.project as pm
    from callimachus.project import create_from_template

    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr(pm, "projects_dir", lambda: projects_root)
    api_deps.clear_project_cache()
    create_from_template("graph_novault", template="thematic", backend="filesystem")

    with TestClient(create_app()) as c:
        r = c.get("/api/projects/graph_novault/graph?cq=cq1")
        assert r.status_code == 404
    api_deps.clear_project_cache()
```

- [ ] **Step 2: Run the new tests to verify they fail**

```
.venv\Scripts\python -m pytest tests/api/test_graph.py::test_graph_returns_dot_for_valid_cq -v 2>&1 | head -20
```

Expected: 404 (route not registered) or import error.

- [ ] **Step 3: Create `callimachus/api/models/graph.py`**

```python
"""Graph viewer response models."""
from __future__ import annotations

from pydantic import BaseModel


class GraphDotOut(BaseModel):
    """Response from GET /projects/{name}/graph — a Graphviz DOT string."""

    dot: str
```

- [ ] **Step 4: Update `callimachus/api/models/__init__.py`**

After the vault imports block, add:

```python
from callimachus.api.models.graph import GraphDotOut
```

Add `"GraphDotOut"` to the `__all__` list.

- [ ] **Step 5: Create `callimachus/api/routers/graph.py`**

```python
"""Graph router — vault subgraph as Graphviz DOT.

GET /projects/{name}/graph?cq={cq_id}

1. Resolve the CQ's SPARQL and run it (SELECT) to collect entity IRIs.
2. Run CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o . FILTER(?s IN (...)) }
3. Transform triples → DOT via vault_view.triples_to_dot.
4. Return GraphDotOut(dot=...).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from callimachus.api.deps import get_project
from callimachus.api.models import GraphDotOut
from callimachus.api.store_cache import (
    StoreCache,
    ensure_vault_ttl,
    resolve_cq_sparql,
)
from callimachus.api.vault_view import all_vault_files, triples_to_dot
from callimachus.engine import ask as ask_engine
from callimachus.project import Project

router = APIRouter(tags=["graph"])

_IRI_RE = re.compile(r"<([^>]+)>")


def _get_store_cache(request: Request) -> StoreCache:
    return request.app.state.store_cache


def _collect_entity_uris(raw: dict) -> list[str]:
    """Pull entity IRIs out of a SELECT or GRAPH SPARQL result dict.

    SELECT rows: values are ``"<http://...>"`` or bare ``"http://..."``
    strings depending on the engine version — handle both.
    GRAPH triples: extract the subject IRI from each triple string.
    """
    uris: list[str] = []
    if raw["kind"] == "select":
        for row in raw["rows"]:
            for val in row.values():
                if not val:
                    continue
                uri = val.strip()
                if uri.startswith("<") and uri.endswith(">"):
                    uri = uri[1:-1]
                if "://" in uri:
                    uris.append(uri)
    elif raw["kind"] == "graph":
        for triple_str in raw["triples"]:
            m = _IRI_RE.match(triple_str.strip())
            if m:
                uris.append(m.group(1))
    return list(dict.fromkeys(uris))  # deduplicate, preserve order


@router.get(
    "/projects/{name}/graph",
    response_model=GraphDotOut,
)
def get_graph(
    cq_id: str = Query(..., alias="cq"),
    project: Project = Depends(get_project),
    cache: StoreCache = Depends(_get_store_cache),
) -> GraphDotOut:
    """Return a CQ's entity neighbourhood as a Graphviz DOT string."""
    try:
        sparql = resolve_cq_sparql(project, cq_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    try:
        ensure_vault_ttl(project)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))

    store = cache.get(project)
    try:
        cq_raw = ask_engine.run_sparql(store, sparql)
    except Exception as exc:
        raise HTTPException(400, f"CQ SPARQL error: {exc}")

    entity_uris = _collect_entity_uris(cq_raw)
    if not entity_uris:
        return GraphDotOut(dot="digraph vault {}")

    in_clause = ", ".join(f"<{u}>" for u in entity_uris)
    construct_sparql = (
        "CONSTRUCT { ?s ?p ?o }\n"
        f"WHERE {{ ?s ?p ?o . FILTER(?s IN ({in_clause})) }}"
    )
    try:
        construct_raw = ask_engine.run_sparql(store, construct_sparql)
    except Exception as exc:
        raise HTTPException(400, f"CONSTRUCT error: {exc}")

    triples = construct_raw.get("triples", [])
    # project.pack.classes is a list of EntityClass objects; .name is the
    # class identifier string used in rdf:type triples. Verify attribute
    # name matches your pack model if this raises AttributeError.
    pack_classes = [c.name for c in project.pack.classes]
    dot = triples_to_dot(triples, pack_classes, all_vault_files(project))
    return GraphDotOut(dot=dot)
```

- [ ] **Step 6: Mount the router in `callimachus/api/main.py`**

In the router imports:

```python
from callimachus.api.routers import (
    inbox,
    jobs,
    pending,
    projects,
    proposals,
    query,
    schema,
    settings,
    vault,
    graph,    # ← add
)
```

In the `for router in (...)` loop, add `graph.router` after `vault.router`:

```python
for router in (
    projects.router,
    schema.router,
    query.router,
    inbox.router,
    pending.router,
    proposals.router,
    vault.router,
    graph.router,     # ← add
    settings.router,
    jobs.router,
):
```

- [ ] **Step 7: Run all graph tests**

```
.venv\Scripts\python -m pytest tests/api/test_graph.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add callimachus/api/models/graph.py callimachus/api/models/__init__.py \
        callimachus/api/routers/graph.py callimachus/api/main.py \
        tests/api/test_graph.py
git commit -m "feat(api): GET /projects/{name}/graph endpoint — CQ subgraph as DOT"
```

---

### Task 3: Extract `PropertiesTable` component

**Files:**
- Create: `frontend/src/components/PropertiesTable.tsx`
- Modify: `frontend/src/routes/VaultPage.tsx`

This is a pure refactor — no behaviour change.

- [ ] **Step 1: Create `frontend/src/components/PropertiesTable.tsx`**

```tsx
import { Badge, Blockquote, Code, Group, Stack, Table, Text } from "@mantine/core";

export function PropertiesTable({
  frontmatter,
}: {
  frontmatter: Record<string, unknown>;
}) {
  const entries = Object.entries(frontmatter ?? {});
  if (entries.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No frontmatter.
      </Text>
    );
  }

  const sourceText =
    typeof frontmatter.source_text === "string"
      ? (frontmatter.source_text as string)
      : null;
  const tableEntries = entries.filter(([k]) => k !== "source_text");

  return (
    <Stack gap="sm">
      <Table withTableBorder withColumnBorders striped="even">
        <Table.Tbody>
          {tableEntries.map(([k, v]) => (
            <Table.Tr key={k}>
              <Table.Td style={{ width: 140, verticalAlign: "top" }}>
                <Code>{k}</Code>
              </Table.Td>
              <Table.Td>
                <PropertyValue value={v} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {sourceText && (
        <Blockquote color="gray" iconSize={16} p="xs" m={0}>
          <Text size="sm">{sourceText}</Text>
        </Blockquote>
      )}
    </Stack>
  );
}

export function PropertyValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return (
      <Text size="sm" c="dimmed">
        —
      </Text>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0)
      return (
        <Text size="sm" c="dimmed">
          [ ]
        </Text>
      );
    return (
      <Group gap={4}>
        {value.map((v, i) => (
          <Badge key={i} variant="default" size="sm">
            {String(v)}
          </Badge>
        ))}
      </Group>
    );
  }
  if (typeof value === "object") {
    return (
      <Code block style={{ fontSize: 12 }}>
        {JSON.stringify(value, null, 2)}
      </Code>
    );
  }
  return <Text size="sm">{String(value)}</Text>;
}
```

- [ ] **Step 2: Update `frontend/src/routes/VaultPage.tsx`**

Add this import near the top of the file:

```tsx
import { PropertiesTable } from "../components/PropertiesTable";
```

Delete the `PropertiesTable` and `PropertyValue` function definitions from `VaultPage.tsx`. They are at the end of the file — search for `function PropertiesTable(` and `function PropertyValue(` and remove both.

- [ ] **Step 3: Verify the Vault page still works**

```bash
cd frontend && npm run dev
```

Open http://localhost:5173, navigate to any project → Vault, click a document, click an entity. Verify the properties table and source-text blockquote render exactly as before.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PropertiesTable.tsx frontend/src/routes/VaultPage.tsx
git commit -m "refactor(frontend): extract PropertiesTable to shared component"
```

---

### Task 4: Extract `GraphvizSvg` component

**Files:**
- Create: `frontend/src/components/GraphvizSvg.tsx`
- Modify: `frontend/src/components/ProposalMiniGraph.tsx`

- [ ] **Step 1: Create `frontend/src/components/GraphvizSvg.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { Alert, Loader, Text } from "@mantine/core";

type VizModule = {
  renderSVGElement(dot: string): SVGSVGElement;
};

let vizInstance: VizModule | null = null;
let vizPromise: Promise<VizModule> | null = null;

async function getViz(): Promise<VizModule> {
  if (vizInstance) return vizInstance;
  if (!vizPromise) {
    vizPromise = import("@viz-js/viz").then(async (mod) => {
      const v = await mod.instance();
      vizInstance = v as unknown as VizModule;
      return vizInstance;
    });
  }
  return vizPromise;
}

/**
 * Render a DOT string as an inline SVG via @viz-js/viz (Graphviz WASM).
 *
 * When ``onNodeClick`` is provided, each ``<g class="node">`` in the SVG
 * gets a click listener. The listener reads the ``<title>`` child (which
 * Graphviz sets to the DOT node ID) and calls
 * ``onNodeClick(decodeURIComponent(title))``. The graph router encodes
 * vault filenames as URL-safe DOT node IDs, so the decoded value is a
 * filename ready for ``GET /vault/files/{filename}``.
 */
export function GraphvizSvg({
  dot,
  onNodeClick,
}: {
  dot: string;
  onNodeClick?: (nodeId: string) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getViz()
      .then((viz) => {
        if (cancelled) return;
        try {
          const svg = viz.renderSVGElement(dot);
          svg.removeAttribute("width");
          svg.removeAttribute("height");
          svg.setAttribute("style", "max-width:100%; height:auto;");
          if (onNodeClick) {
            svg.querySelectorAll("g.node").forEach((g) => {
              const title = g.querySelector("title")?.textContent;
              if (!title) return;
              (g as SVGGElement).style.cursor = "pointer";
              g.addEventListener("click", (e) => {
                e.stopPropagation();
                onNodeClick(decodeURIComponent(title));
              });
            });
          }
          if (hostRef.current) {
            hostRef.current.replaceChildren(svg);
          }
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setLoading(false);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setError((e as Error).message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dot, onNodeClick]);

  if (error) {
    return (
      <Alert color="yellow" variant="light">
        <Text size="xs">Graph render failed: {error}</Text>
      </Alert>
    );
  }
  return (
    <div
      style={{
        minHeight: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {loading && <Loader size="xs" />}
      <div
        ref={hostRef}
        style={{
          width: "100%",
          display: loading ? "none" : "flex",
          justifyContent: "center",
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Simplify `frontend/src/components/ProposalMiniGraph.tsx`**

Replace the entire file with:

```tsx
import { GraphvizSvg } from "./GraphvizSvg";

export function ProposalMiniGraph({ dot }: { dot: string }) {
  return <GraphvizSvg dot={dot} />;
}
```

- [ ] **Step 3: Verify the Proposals page still renders graphs**

```bash
cd frontend && npm run dev
```

Navigate to a project → Proposals. Any proposal with a DOT graph should render identically.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/GraphvizSvg.tsx frontend/src/components/ProposalMiniGraph.tsx
git commit -m "refactor(frontend): extract GraphvizSvg with onNodeClick support"
```

---

### Task 5: `useVaultGraph` hook and `GraphDotOut` TypeScript type

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/hooks.ts`

- [ ] **Step 1: Add `GraphDotOut` to `frontend/src/api/types.ts`**

Append after the vault browser section (after the `VaultFileOut` interface):

```ts
// ---------- Graph viewer --------------------------------------------------

export interface GraphDotOut {
  dot: string;
}
```

- [ ] **Step 2: Add `GraphDotOut` to the imports in `frontend/src/api/hooks.ts`**

In the import block at the top of `hooks.ts`, add `GraphDotOut` to the list of types imported from `"./types"`.

- [ ] **Step 3: Add `vaultGraph` to the `qk` object in `hooks.ts`**

In the `qk` object (after `vaultFile`), add:

```ts
vaultGraph: (name: string, cqId: string) =>
  ["projects", name, "graph", cqId] as const,
```

- [ ] **Step 4: Add `useVaultGraph` hook to `hooks.ts`**

After the `useVaultFile` hook (in the "Vault browser" section), add:

```ts
export function useVaultGraph(
  name: string | undefined,
  cqId: string | undefined,
) {
  return useQuery({
    queryKey:
      name && cqId
        ? qk.vaultGraph(name, cqId)
        : ["projects", "__none__", "graph", "__none__"],
    queryFn: () =>
      api.get<GraphDotOut>(
        `/projects/${name}/graph?cq=${encodeURIComponent(cqId!)}`,
      ),
    enabled: !!name && !!cqId,
  });
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -15
```

Expected: no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/hooks.ts
git commit -m "feat(frontend): useVaultGraph hook and GraphDotOut type"
```

---

### Task 6: `GraphPage.tsx` and nav wiring

**Files:**
- Create: `frontend/src/routes/GraphPage.tsx`
- Modify: `frontend/src/components/ProjectShell.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/routes/GraphPage.tsx`**

```tsx
import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Divider,
  Drawer,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconNetwork } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useActiveProject } from "../state/useActiveProject";
import { useRebuildTtl, useVaultFile, useVaultGraph } from "../api/hooks";
import { GraphvizSvg } from "../components/GraphvizSvg";
import { PropertiesTable } from "../components/PropertiesTable";

export function GraphPage() {
  const { projectName, data: project } = useActiveProject();
  const [selectedCqId, setSelectedCqId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [drawerOpened, { open: openDrawer, close: closeDrawer }] =
    useDisclosure(false);

  const cqs = project?.pack.competency_questions ?? [];

  const {
    data: graphData,
    isPending: graphLoading,
    error: graphError,
  } = useVaultGraph(projectName, selectedCqId ?? undefined);

  const rebuildTtl = useRebuildTtl(projectName);

  function handleNodeClick(filename: string) {
    setSelectedFilename(filename);
    openDrawer();
  }

  const isEmpty = graphData && !graphData.dot.includes("[label=");

  return (
    <Stack>
      <Group gap="xs" align="baseline">
        <IconNetwork size={20} />
        <Title order={2}>Graph</Title>
        <Text size="sm" c="dimmed">
          Entity relationships from the approved vault.
        </Text>
      </Group>

      {cqs.length === 0 && (
        <Alert color="gray" variant="light">
          No competency questions defined in this pack.
        </Alert>
      )}

      {cqs.length > 0 && (
        <Stack gap="xs">
          <Text size="sm" fw={500}>
            Select a question to explore:
          </Text>
          <Group gap="xs">
            {cqs.map((cq) => (
              <UnstyledButton
                key={cq.id}
                onClick={() => setSelectedCqId(cq.id)}
                p="xs"
                style={{
                  borderRadius: 6,
                  background:
                    selectedCqId === cq.id
                      ? "var(--mantine-color-indigo-light)"
                      : "var(--mantine-color-default-hover)",
                  border:
                    selectedCqId === cq.id
                      ? "1px solid var(--mantine-color-indigo-4)"
                      : "1px solid transparent",
                }}
              >
                <Text size="sm" fw={selectedCqId === cq.id ? 600 : 400}>
                  {cq.label}
                </Text>
              </UnstyledButton>
            ))}
          </Group>
        </Stack>
      )}

      {!selectedCqId && cqs.length > 0 && (
        <Text size="sm" c="dimmed">
          Select a question above to render its subgraph.
        </Text>
      )}

      {selectedCqId && graphLoading && (
        <Group gap="xs">
          <Loader size="sm" />
          <Text c="dimmed" size="sm">
            Building graph…
          </Text>
        </Group>
      )}

      {selectedCqId && graphError && (
        <Alert color="red" variant="light" title="Failed to load graph">
          <Stack gap="xs">
            <Text size="sm">{(graphError as Error).message}</Text>
            <Button
              size="xs"
              variant="light"
              loading={rebuildTtl.isPending}
              onClick={() => rebuildTtl.mutate()}
            >
              Rebuild vault TTL
            </Button>
          </Stack>
        </Alert>
      )}

      {selectedCqId && isEmpty && (
        <Alert color="gray" variant="light">
          No entities matched this question.
        </Alert>
      )}

      {selectedCqId && graphData && !isEmpty && (
        <Box>
          <GraphvizSvg dot={graphData.dot} onNodeClick={handleNodeClick} />
        </Box>
      )}

      <Drawer
        opened={drawerOpened}
        onClose={closeDrawer}
        position="right"
        title="Entity detail"
        size="md"
      >
        {selectedFilename && projectName && (
          <EntityDrawer
            projectName={projectName}
            filename={selectedFilename}
            onClose={closeDrawer}
          />
        )}
      </Drawer>
    </Stack>
  );
}

function EntityDrawer({
  projectName,
  filename,
  onClose,
}: {
  projectName: string;
  filename: string;
  onClose: () => void;
}) {
  const { data, isPending, error } = useVaultFile(projectName, filename);

  if (isPending) {
    return (
      <Group gap="xs">
        <Loader size="xs" />
        <Text c="dimmed" size="sm">
          Loading…
        </Text>
      </Group>
    );
  }

  if (error) {
    return (
      <Alert color="red" variant="light" title="Entity not found">
        {(error as Error).message}
      </Alert>
    );
  }

  if (!data) return null;

  return (
    <Stack gap="md">
      <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
        {filename}
      </Text>
      <ScrollArea.Autosize mah="70vh">
        <Stack gap="md">
          <PropertiesTable frontmatter={data.frontmatter} />
          {data.body.trim() && (
            <>
              <Divider label="Body" />
              <Box className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {data.body}
                </ReactMarkdown>
              </Box>
            </>
          )}
        </Stack>
      </ScrollArea.Autosize>
      <Button
        component={Link}
        to={`/projects/${projectName}/vault`}
        variant="light"
        size="sm"
        onClick={onClose}
      >
        View in Vault →
      </Button>
    </Stack>
  );
}
```

- [ ] **Step 2: Add Graph to the nav in `frontend/src/components/ProjectShell.tsx`**

Add `IconNetwork` to the tabler-icons import:

```tsx
import {
  IconChartDots3,
  IconLayoutGrid,
  IconLayoutSidebar,
  IconListSearch,
  IconNetwork,       // ← add
  IconSchema,
  IconSettings,
} from "@tabler/icons-react";
```

In the `NAV` array, insert the Graph entry between Vault and Query:

```ts
const NAV: { label: string; to: string; icon: React.ReactNode }[] = [
  { label: "Dashboard", to: "dashboard", icon: <IconLayoutGrid size={16} /> },
  { label: "Schema",    to: "schema",    icon: <IconSchema size={16} /> },
  { label: "Vault",     to: "vault",     icon: <IconLayoutSidebar size={16} /> },
  { label: "Graph",     to: "graph",     icon: <IconNetwork size={16} /> },   // ← add
  { label: "Query",     to: "query",     icon: <IconListSearch size={16} /> },
  { label: "Proposals", to: "proposals", icon: <IconChartDots3 size={16} /> },
  { label: "Settings",  to: "settings",  icon: <IconSettings size={16} /> },
];
```

- [ ] **Step 3: Register the route in `frontend/src/App.tsx`**

Add the import:

```tsx
import { GraphPage } from "./routes/GraphPage";
```

Add the route inside the `projects/:projectName` block, between vault and proposals:

```tsx
<Route path="vault"      element={<VaultPage />} />
<Route path="graph"      element={<GraphPage />} />   {/* ← add */}
<Route path="proposals"  element={<ProposalsPage />} />
```

- [ ] **Step 4: Verify TypeScript builds clean**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 5: Manual smoke test**

Start both backend and frontend:

```bash
# Terminal 1 — backend
.venv\Scripts\uvicorn callimachus.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Test the golden path:

1. Open http://localhost:5173 and navigate to the `compliance` project.
2. Click **Graph** in the sidebar — verify the page loads with a CQ picker.
3. Click one of the CQ buttons — verify a loading indicator appears, then a graph SVG renders.
4. Click a node in the graph — verify the right-side drawer opens showing the entity's frontmatter table and source text.
5. Click **View in Vault →** inside the drawer — verify it navigates to the Vault page.
6. Navigate back; click **Vault** — verify the Vault page's properties table still renders (PropertiesTable refactor regression).
7. Navigate to **Proposals** — verify proposal mini-graphs still render (GraphvizSvg refactor regression).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/GraphPage.tsx \
        frontend/src/components/ProjectShell.tsx \
        frontend/src/App.tsx
git commit -m "feat(frontend): Graph page — CQ picker, Graphviz renderer, entity drawer"
```
