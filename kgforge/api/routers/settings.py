"""Settings router — read-only env snapshot + cache invalidation."""
from __future__ import annotations

import os

from fastapi import APIRouter

from kgforge.api.deps import clear_project_cache
from kgforge.api.models import SettingsOut
from kgforge.pack.loader import load_builtin
from kgforge.project import projects_dir, repo_root

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return SettingsOut(
        api_key_set=bool(os.environ.get("ANTHROPIC_API_KEY")),
        repo_root=str(repo_root()),
        projects_dir=str(projects_dir()),
    )


@router.post("/settings/cache/clear")
def clear_caches() -> dict[str, bool]:
    """Drop pack + project caches. Useful after editing pack.yaml on disk."""
    load_builtin.cache_clear()
    clear_project_cache()
    return {"cleared": True}
