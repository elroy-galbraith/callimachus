"""Settings router — read-only env snapshot + cache invalidation."""
from __future__ import annotations

import os

from fastapi import APIRouter

from callimachus.api.deps import clear_project_cache
from callimachus.api.models import ProviderStatus, SettingsOut
from callimachus.pack.loader import load_builtin
from callimachus.project import projects_dir, repo_root
from callimachus.providers import PROVIDERS

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    providers = [
        ProviderStatus(
            id=p.id,
            label=p.label,
            env_var=p.env_var,
            configured=bool(os.environ.get(p.env_var, "").strip()),
        )
        for p in PROVIDERS
    ]
    return SettingsOut(
        api_key_set=any(p.configured for p in providers),
        providers=providers,
        repo_root=str(repo_root()),
        projects_dir=str(projects_dir()),
    )


@router.post("/settings/cache/clear")
def clear_caches() -> dict[str, bool]:
    """Drop pack + project caches. Useful after editing pack.yaml on disk."""
    load_builtin.cache_clear()
    clear_project_cache()
    return {"cleared": True}
