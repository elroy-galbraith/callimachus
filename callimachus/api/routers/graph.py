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
    """Pull entity IRIs out of a SELECT or GRAPH SPARQL result dict."""
    uris: list[str] = []
    kind = raw.get("kind")
    if kind == "select":
        for row in raw.get("rows", []):
            for val in row.values():
                if not val:
                    continue
                uri = val.strip()
                if uri.startswith("<") and uri.endswith(">"):
                    uri = uri[1:-1]
                    if "://" in uri and ">" not in uri and not any(c.isspace() for c in uri):
                        uris.append(uri)
    elif kind == "graph":
        for triple_str in raw.get("triples", []):
            m = _IRI_RE.match(triple_str.strip())
            if m:
                uri = m.group(1)
                if ">" not in uri and not any(c.isspace() for c in uri):
                    uris.append(uri)
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
    pack_classes = [c.name for c in project.pack.classes]
    dot = triples_to_dot(triples, pack_classes, all_vault_files(project))
    return GraphDotOut(dot=dot)
