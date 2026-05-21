"""Projects router — list, detail, create, mutate pack settings."""
from __future__ import annotations

import yaml
from fastapi import APIRouter, Depends, HTTPException

from callimachus.api.deps import clear_project_cache, get_project
from callimachus.api.models import (
    DomainPackOut,
    ModelsUpdateIn,
    PackTemplateOut,
    ProjectCreateIn,
    ProjectDetail,
    ProjectSummary,
)
from callimachus.pack import load_builtin, load_pack
from callimachus.pack.loader import BUILTIN_DIR
from callimachus.project import Project, create_from_template, list_projects

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectSummary])
def list_all() -> list[ProjectSummary]:
    return [ProjectSummary(**p) for p in list_projects()]


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create(body: ProjectCreateIn) -> ProjectDetail:
    try:
        project = create_from_template(
            body.name,
            template=body.template,
            label=body.label,
            backend=body.backend,
        )
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        # Missing template
        raise HTTPException(status_code=400, detail=str(e))
    clear_project_cache()
    return ProjectDetail.from_project(project)


@router.get("/projects/templates", response_model=list[PackTemplateOut])
def list_templates() -> list[PackTemplateOut]:
    """Built-in pack templates that ``POST /api/projects`` can scaffold from."""
    out: list[PackTemplateOut] = []
    for child in sorted(BUILTIN_DIR.iterdir()):
        if not (child / "pack.yaml").exists():
            continue
        try:
            pack = load_builtin(child.name)
        except Exception:
            continue
        out.append(
            PackTemplateOut(
                name=pack.metadata.name,
                label=pack.metadata.label,
                description=pack.metadata.description,
            )
        )
    return out


@router.get("/projects/{name}", response_model=ProjectDetail)
def detail(project: Project = Depends(get_project)) -> ProjectDetail:
    return ProjectDetail.from_project(project)


def _pack_response(pack, project: Project) -> DomainPackOut:
    """Shape a pack for the Schema page (CQ SPARQL inlined)."""
    return DomainPackOut.from_pack(
        pack,
        include_cq_text=True,
        sparql_dir=project.sparql_dir,
    )


@router.get("/projects/{name}/pack", response_model=DomainPackOut)
def project_pack(project: Project = Depends(get_project)) -> DomainPackOut:
    """Pack snapshot with competency-question SPARQL inlined.

    Used by the Schema page; split from the project detail so the (potentially
    large) CQ bodies don't ride along on every project-list refresh.
    """
    return _pack_response(project.pack, project)


@router.patch("/projects/{name}/pack/models", response_model=DomainPackOut)
def update_pack_models(
    body: ModelsUpdateIn,
    project: Project = Depends(get_project),
) -> DomainPackOut:
    """Update ``models.extractor`` / ``models.ask`` in the project's pack.yaml.

    Refuses to mutate built-in packs (those shipped under
    ``callimachus/pack/builtin/``) -- projects using a built-in template
    must first materialise a local copy. Recreating the project from the
    same template via ``POST /api/projects`` does that.
    """
    pack_dir = project.pack.pack_dir
    if pack_dir is None:
        raise HTTPException(
            status_code=400,
            detail="project has no on-disk pack directory; cannot mutate",
        )
    try:
        pack_dir.resolve().relative_to(BUILTIN_DIR.resolve())
        is_builtin = True
    except ValueError:
        is_builtin = False
    if is_builtin:
        raise HTTPException(
            status_code=400,
            detail=(
                "This project uses a built-in pack template, which is "
                "read-only. Recreate the project from the same template "
                "to materialise an editable copy, then retry."
            ),
        )

    yaml_path = pack_dir / "pack.yaml"
    try:
        original_text = yaml_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"pack.yaml missing at {yaml_path}")

    data = yaml.safe_load(original_text) or {}
    models = dict(data.get("models") or {})
    if body.extractor is not None:
        models["extractor"] = body.extractor.strip()
    if body.ask is not None:
        models["ask"] = body.ask.strip()
    data["models"] = models

    new_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    yaml_path.write_text(new_text, encoding="utf-8")

    # If the new pack fails to validate (e.g. an empty string slipped
    # through), restore the original file so the project keeps working
    # -- pydantic's error surfaces as a 400.
    try:
        refreshed = load_pack(pack_dir)
    except Exception as exc:  # noqa: BLE001
        yaml_path.write_text(original_text, encoding="utf-8")
        raise HTTPException(
            status_code=400, detail=f"updated pack.yaml failed validation: {exc}"
        )

    clear_project_cache()
    return _pack_response(refreshed, project)
