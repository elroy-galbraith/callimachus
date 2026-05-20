"""Projects router — list, detail, create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from callimachus.api.deps import clear_project_cache, get_project
from callimachus.api.models import (
    DomainPackOut,
    PackTemplateOut,
    ProjectCreateIn,
    ProjectDetail,
    ProjectSummary,
)
from callimachus.pack import load_builtin
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


@router.get("/projects/{name}/pack", response_model=DomainPackOut)
def project_pack(project: Project = Depends(get_project)) -> DomainPackOut:
    """Pack snapshot with competency-question SPARQL inlined.

    Used by the Schema page; split from the project detail so the (potentially
    large) CQ bodies don't ride along on every project-list refresh.
    """
    return DomainPackOut.from_pack(
        project.pack,
        include_cq_text=True,
        sparql_dir=project.sparql_dir,
    )
