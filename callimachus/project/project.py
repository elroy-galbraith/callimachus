"""Project = pack + paths + approval backend.

Storage: each project is a folder containing a project.json. Paths in
project.json may be relative (resolved against the project folder) or
absolute. The repo also recognises a "legacy mode" where the existing
carib-comp-ont vault/inbox layout lives at the repo root with a
projects/compliance/project.json pointing back at it.

Built-in templates ship at callimachus/pack/builtin/<name>/; "create from
template" copies the pack into the new project folder so users can edit
it without touching the shipped defaults.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from callimachus.approval import ApprovalBackend, make_backend
from callimachus.pack import DomainPack, load_builtin, load_pack
from callimachus.pack.loader import BUILTIN_DIR


@dataclass
class Project:
    """Runtime view of a project — pack, paths, approval backend.

    Construct via load_project() / create_from_template(); don't __init__
    directly unless you know what you're doing.
    """
    name: str
    label: str
    project_dir: Path
    pack: DomainPack
    vault_dir: Path
    inbox_dir: Path
    sources_dir: Path
    schema_ttl: Path | None
    sparql_dir: Path | None
    approval_config: dict[str, Any] = field(default_factory=dict)

    @cached_property
    def approval(self) -> ApprovalBackend:
        cfg = dict(self.approval_config)
        backend_name = cfg.pop("backend", "filesystem")
        # Inject paths the backend needs and isn't told via JSON.
        if backend_name == "filesystem":
            cfg.setdefault("vault_dir", self.vault_dir)
        elif backend_name == "git":
            # Honour an explicit "repo_root" in approval config (relative
            # paths resolve against the project dir); otherwise auto-detect
            # by walking up from the vault until we find a .git/. Falling
            # back to project_dir is a last resort that will likely fail
            # at gitpython instantiation — but at least with a clear
            # error from the git backend itself rather than a silent miss.
            explicit = cfg.pop("repo_root", None)
            if explicit is not None:
                explicit_path = Path(explicit)
                cfg["repo_root"] = (
                    explicit_path if explicit_path.is_absolute()
                    else (self.project_dir / explicit_path).resolve()
                )
            else:
                cfg["repo_root"] = _find_git_root(self.vault_dir) or self.project_dir
        return make_backend(backend_name, **cfg)

    @cached_property
    def vault_ttl(self) -> Path:
        """Where to_turtle writes its output (next to the vault)."""
        return self.vault_dir / "vault.ttl"

    @property
    def has_inbox(self) -> bool:
        return self.inbox_dir.exists()

    def ensure_dirs(self) -> None:
        """Create vault/inbox/sources if missing (idempotent)."""
        for d in (self.vault_dir, self.inbox_dir, self.sources_dir):
            d.mkdir(parents=True, exist_ok=True)


# ── Resolution helpers ────────────────────────────────────────────────────────


def _resolve(base: Path, p: str) -> Path:
    """Resolve a path string from project.json against the project folder."""
    pp = Path(p)
    return pp if pp.is_absolute() else (base / pp).resolve()


def _find_git_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a directory containing `.git`.

    Returns the directory containing .git, or None if we hit the filesystem
    root first. Used by the git approval backend to locate the repo when
    the project.json doesn't pin it explicitly.
    """
    cur = Path(start).resolve()
    for parent in (cur, *cur.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _resolve_pack(project_dir: Path, pack_spec: str) -> DomainPack:
    """A pack spec is either:
        - "builtin/<name>"            → ship-bundled pack
        - "<relative>" or "<absolute>"→ a folder containing pack.yaml
    """
    if pack_spec.startswith("builtin/"):
        return load_builtin(pack_spec.removeprefix("builtin/"))
    pack_dir = _resolve(project_dir, pack_spec)
    return load_pack(pack_dir)


# ── Repo-root convention ──────────────────────────────────────────────────────


def repo_root() -> Path:
    """The folder this checkout lives in (one level up from the callimachus package)."""
    return Path(__file__).resolve().parent.parent.parent


def projects_dir() -> Path:
    """All projects live under <repo_root>/projects/. Created on first access."""
    d = repo_root() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Public API ────────────────────────────────────────────────────────────────


def load_project(name_or_path: str | Path) -> Project:
    """Load a project by name (under projects/<name>/) or by absolute path."""
    p = Path(name_or_path)
    if not p.is_absolute() and not p.exists():
        p = projects_dir() / str(name_or_path)
    project_dir = p.resolve()
    json_path = project_dir / "project.json"
    if not json_path.exists():
        raise FileNotFoundError(f"project.json not found in {project_dir}")

    cfg = json.loads(json_path.read_text(encoding="utf-8"))
    pack = _resolve_pack(project_dir, cfg["pack"])
    return Project(
        name=cfg["name"],
        label=cfg.get("label", cfg["name"]),
        project_dir=project_dir,
        pack=pack,
        vault_dir=_resolve(project_dir, cfg.get("vault_dir", "vault")),
        inbox_dir=_resolve(project_dir, cfg.get("inbox_dir", "inbox")),
        sources_dir=_resolve(project_dir, cfg.get("sources_dir", "vault/sources")),
        schema_ttl=_resolve(project_dir, cfg["schema_ttl"]) if cfg.get("schema_ttl") else None,
        sparql_dir=_resolve(project_dir, cfg["sparql_dir"]) if cfg.get("sparql_dir") else None,
        approval_config=cfg.get("approval") or {"backend": "filesystem"},
    )


def list_projects() -> list[dict[str, str]]:
    """Return [{name, label, dir}, …] for every project under projects/."""
    out: list[dict[str, str]] = []
    for child in sorted(projects_dir().iterdir()):
        json_path = child / "project.json"
        if not json_path.exists():
            continue
        try:
            cfg = json.loads(json_path.read_text(encoding="utf-8"))
            out.append(
                {
                    "name": cfg.get("name", child.name),
                    "label": cfg.get("label", cfg.get("name", child.name)),
                    "dir": str(child),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return out


def create_from_template(
    name: str,
    template: str = "compliance",
    *,
    label: str | None = None,
    backend: str = "filesystem",
) -> Project:
    """Scaffold a new project under projects/<name>/.

    Copies the template pack into the project folder so users can edit it
    without touching the built-in defaults. Layout:

        projects/<name>/
        ├── project.json
        ├── pack/                  ← copy of callimachus/pack/builtin/<template>/
        │   ├── pack.yaml
        │   ├── hooks.py?
        │   ├── schema.ttl?
        │   └── sparql/?
        ├── vault/
        ├── inbox/
        └── vault/sources/
    """
    project_dir = projects_dir() / name
    if project_dir.exists():
        raise FileExistsError(f"project already exists: {project_dir}")

    project_dir.mkdir(parents=True)
    template_dir = BUILTIN_DIR / template
    if not template_dir.exists():
        raise FileNotFoundError(f"unknown template: {template}")

    shutil.copytree(template_dir, project_dir / "pack")

    # Pack-relative schema.ttl + sparql/ if the template has them; else None.
    schema_ttl_rel = None
    if (project_dir / "pack" / "schema.ttl").exists():
        schema_ttl_rel = "pack/schema.ttl"
    sparql_dir_rel = None
    if (project_dir / "pack" / "sparql").exists():
        sparql_dir_rel = "pack/sparql"

    cfg: dict[str, Any] = {
        "name": name,
        "label": label or name.replace("_", " ").title(),
        "pack": "pack",  # relative to project dir
        "vault_dir": "vault",
        "inbox_dir": "inbox",
        "sources_dir": "vault/sources",
        "approval": {"backend": backend},
    }
    if schema_ttl_rel:
        cfg["schema_ttl"] = schema_ttl_rel
    if sparql_dir_rel:
        cfg["sparql_dir"] = sparql_dir_rel

    (project_dir / "project.json").write_text(
        json.dumps(cfg, indent=2) + "\n", encoding="utf-8"
    )

    project = load_project(project_dir)
    project.ensure_dirs()
    return project
