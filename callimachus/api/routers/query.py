"""Query router — SPARQL execution + NL ask job.

Three sync endpoints (rebuild-ttl, sparql, run-cq) and one job endpoint
(ask). The NL ask flow is the first real exercise of the JobRegistry +
SSE stream; the orchestrator emits one ``progress`` event per pipeline
stage so the UI can stream "Synthesising… / Executing… / Summarising…"
without polling.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from callimachus.api.deps import get_jobs, get_project
from callimachus.api.jobs import JobRegistry, JobState
from callimachus.api.models import (
    AskResultOut,
    CqRunResult,
    GraphResultOut,
    NLAnswerOut,
    NLQueryIn,
    SelectResultOut,
    SparqlQueryIn,
    SparqlResultOut,
    VaultTtlOut,
)
from callimachus.api.store_cache import (
    StoreCache,
    ensure_vault_ttl,
    rebuild_vault_ttl,
    resolve_cq_sparql,
)
from callimachus.engine import ask as ask_engine
from callimachus.project import Project

router = APIRouter(tags=["query"])


def get_store_cache(request: Request) -> StoreCache:
    return request.app.state.store_cache


def _coerce_result(raw: dict) -> SparqlResultOut:
    """Wrap the engine's plain dict in the right Pydantic model.

    ``ask.run_sparql`` returns ``{"kind": "select"|"ask"|"graph", ...}``;
    Pydantic's discriminated union does the dispatch on serialisation.
    """
    kind = raw.get("kind")
    if kind == "select":
        return SelectResultOut(
            variables=raw.get("variables", []),
            rows=raw.get("rows", []),
        )
    if kind == "ask":
        return AskResultOut(value=bool(raw["value"]))
    if kind == "graph":
        return GraphResultOut(triples=list(raw.get("triples", [])))
    raise HTTPException(500, f"unexpected SPARQL result kind: {kind!r}")


@router.post(
    "/projects/{name}/query/rebuild-ttl",
    response_model=VaultTtlOut,
)
def rebuild_ttl(
    project: Project = Depends(get_project),
    cache: StoreCache = Depends(get_store_cache),
) -> VaultTtlOut:
    """Drop ``vault.ttl`` and regenerate it from the markdown vault."""
    try:
        size = rebuild_vault_ttl(project)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    cache.invalidate(project.name)
    return VaultTtlOut(rebuilt=True, size_bytes=size)


@router.post(
    "/projects/{name}/query/sparql",
    response_model=SparqlResultOut,
)
def run_sparql(
    body: SparqlQueryIn,
    project: Project = Depends(get_project),
    cache: StoreCache = Depends(get_store_cache),
) -> SparqlResultOut:
    """Execute a free-form SPARQL query."""
    try:
        ensure_vault_ttl(project)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    store = cache.get(project)
    try:
        raw = ask_engine.run_sparql(store, body.sparql)
    except Exception as exc:
        raise HTTPException(400, f"SPARQL error: {exc}")
    return _coerce_result(raw)


@router.post(
    "/projects/{name}/query/competency-questions/{cq_id}/run",
    response_model=CqRunResult,
)
def run_competency_question(
    cq_id: str,
    project: Project = Depends(get_project),
    cache: StoreCache = Depends(get_store_cache),
) -> CqRunResult:
    """Run a named competency question against the project's graph."""
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
    raw = ask_engine.run_sparql(store, sparql)
    return CqRunResult(cq_id=cq_id, sparql=sparql, result=_coerce_result(raw))


@router.post(
    "/projects/{name}/query/ask",
    status_code=202,
)
def kick_nl_ask(
    body: NLQueryIn,
    bg: BackgroundTasks,
    project: Project = Depends(get_project),
    cache: StoreCache = Depends(get_store_cache),
    jobs: JobRegistry = Depends(get_jobs),
) -> dict[str, str]:
    """Kick off a natural-language ask job. Returns ``{job_id}``.

    Poll ``GET /api/jobs/{job_id}`` or subscribe to
    ``GET /api/jobs/{job_id}/events`` (SSE) for streaming progress.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="ANTHROPIC_API_KEY not set; can't run NL ask. Set it in .env.",
        )
    if not body.question.strip():
        raise HTTPException(400, "question must not be empty")
    job = jobs.create("nl_ask")
    bg.add_task(_run_nl_ask, job, project, cache, body)
    return {"job_id": job.id}


def _run_nl_ask(
    job: JobState,
    project: Project,
    cache: StoreCache,
    body: NLQueryIn,
) -> None:
    """Orchestrate ``synthesize_sparql -> run_sparql -> summarise``.

    Emits one ``progress`` event per stage so the SSE drawer can render a
    live trace. The terminal result is the full ``NLAnswerOut`` dict.
    """
    model = body.model or project.pack.models.ask
    job.set_status("running")
    try:
        job.emit("info", "Ensuring vault.ttl is built…")
        ensure_vault_ttl(project)

        job.emit("info", "Loading graph into pyoxigraph…")
        store = cache.get(project)

        job.emit("info", "Building entity catalog and few-shot examples…")
        catalog = ask_engine.entity_catalog(store, project.pack)
        examples = ask_engine.few_shot_examples(project.pack)

        schema_text = (
            project.schema_ttl.read_text(encoding="utf-8")
            if project.schema_ttl and project.schema_ttl.exists()
            else "(no schema TTL)"
        )

        job.emit(
            "info",
            f"Synthesising SPARQL via {model}…",
            {"stage": "synthesise", "model": model},
        )
        sparql, rationale = ask_engine.synthesize_sparql(
            model, body.question, schema_text, catalog, examples
        )
        job.emit(
            "info",
            "SPARQL ready",
            {"stage": "synthesise.done", "sparql": sparql, "rationale": rationale},
        )

        job.emit("info", "Executing SPARQL…", {"stage": "execute"})
        raw = ask_engine.run_sparql(store, sparql)
        row_count = (
            len(raw.get("rows", []))
            if raw["kind"] == "select"
            else 1
            if raw["kind"] == "ask"
            else len(raw.get("triples", []))
        )
        job.emit(
            "info",
            f"{row_count} row(s) / triple(s)",
            {"stage": "execute.done", "row_count": row_count, "kind": raw["kind"]},
        )

        job.emit("info", f"Summarising via {model}…", {"stage": "summarise"})
        answer = ask_engine.summarise(
            model, body.question, sparql, rationale, raw
        )

        out = NLAnswerOut(
            question=body.question,
            sparql=sparql,
            rationale=rationale,
            result=_coerce_result(raw),
            answer=answer,
        )
        job.set_status("done", result=out.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001
        job.emit("error", f"NL ask failed: {exc}")
        job.set_status("error", error=str(exc))
