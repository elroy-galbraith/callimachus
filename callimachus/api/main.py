"""FastAPI app factory + lifespan + CORS.

Run with:
    uvicorn callimachus.api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from callimachus.api.jobs import JobRegistry
from callimachus.api.routers import (
    inbox,
    jobs,
    pending,
    projects,
    proposals,
    query,
    schema,
    settings,
)
from callimachus.api.store_cache import StoreCache

# Load .env so engine modules see ANTHROPIC_API_KEY. Match the Streamlit
# convention (no override) — values pre-set in the shell win over .env.
try:
    from dotenv import load_dotenv

    _REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass


# CORS — Vite dev server on 5173 is the only origin we need. The Vite proxy
# (see frontend/vite.config.ts) makes this technically redundant in dev,
# but leaving CORS on costs nothing and covers the build-and-serve case.
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "KGFORGE_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.jobs = JobRegistry()
    app.state.store_cache = StoreCache()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="callimachus",
        version="0.1.0",
        description=(
            "HTTP API for callimachus: configurable PDF → typed-entities → graph → "
            "query platform. Wraps the callimachus.engine package; consumed by the "
            "React frontend under ../frontend/."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        projects.router,
        schema.router,
        query.router,
        inbox.router,
        pending.router,
        proposals.router,
        settings.router,
        jobs.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
