"""Project + DomainPack response/request models."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from kgforge.pack import DomainPack
from kgforge.project import Project


class ProjectSummary(BaseModel):
    """Cheap view used by the project list — no pack details."""

    name: str
    label: str
    dir: str


class EntityClassOut(BaseModel):
    name: str
    label: str
    description: str | None = None
    parent: str | None = None
    iri: str


class EntityPropertyOut(BaseModel):
    name: str
    label: str | None = None
    domain: str | None = None
    range: str | None = None
    datatype: bool = False
    prompt_hint: str | None = None
    predicate_iri: str


class CompetencyQuestionOut(BaseModel):
    id: str
    label: str
    file: str
    sparql: str | None = None  # inlined body if the .rq file is present


class PromptSpecOut(BaseModel):
    """Raw prompt templates from the pack (no rendering)."""

    version: str
    system: str
    user: str
    few_shot: str
    text_window_chars: int


class DomainPackOut(BaseModel):
    """Pack snapshot for the Schema page — internal fields stripped."""

    name: str
    label: str
    description: str | None = None
    version: str
    author: str | None = None
    base_iri: str
    entity_iri: str
    prefix: str
    entity_prefix: str
    classes: list[EntityClassOut]
    properties: list[EntityPropertyOut]
    competency_questions: list[CompetencyQuestionOut]
    prompt: PromptSpecOut
    extractor_model: str
    ask_model: str
    accepted_extensions: list[str]

    @classmethod
    def from_pack(
        cls,
        pack: DomainPack,
        *,
        include_cq_text: bool = False,
        sparql_dir: Path | None = None,
    ) -> "DomainPackOut":
        """Wrap a ``DomainPack`` for the wire.

        ``include_cq_text`` inlines the SPARQL body of each competency
        question. Resolution mirrors the Streamlit Query page:
        pack-relative first (``pack.pack_dir / cq.file``), then a fallback
        to ``sparql_dir / basename(cq.file)`` for legacy projects that
        keep SPARQL files outside the pack (e.g. ``projects/compliance``).
        """
        # Local import: store_cache imports DomainPack at type-check
        # time, which would be circular if imported at module scope.
        from kgforge.api.store_cache import resolve_cq_path

        cqs: list[CompetencyQuestionOut] = []
        for cq in pack.competency_questions:
            sparql: str | None = None
            if include_cq_text:
                path = resolve_cq_path(pack, cq, sparql_dir)
                if path is not None:
                    sparql = path.read_text(encoding="utf-8")
            cqs.append(
                CompetencyQuestionOut(
                    id=cq.id, label=cq.label, file=cq.file, sparql=sparql
                )
            )
        return cls(
            name=pack.metadata.name,
            label=pack.metadata.label,
            description=pack.metadata.description,
            version=pack.metadata.version,
            author=pack.metadata.author,
            base_iri=pack.namespaces.base_iri,
            entity_iri=pack.namespaces.entity_iri,
            prefix=pack.namespaces.prefix,
            entity_prefix=pack.namespaces.entity_prefix,
            classes=[
                EntityClassOut(
                    name=c.name,
                    label=c.label,
                    description=c.description,
                    parent=c.parent,
                    iri=pack.class_iri(c.name),
                )
                for c in pack.classes
            ],
            properties=[
                EntityPropertyOut(
                    name=p.name,
                    label=p.label,
                    domain=p.domain,
                    range=p.range,
                    datatype=p.datatype,
                    prompt_hint=p.prompt_hint,
                    predicate_iri=pack.property_iri(p.name),
                )
                for p in pack.properties
            ],
            competency_questions=cqs,
            prompt=PromptSpecOut(
                version=pack.prompt.version,
                system=pack.prompt.system,
                user=pack.prompt.user,
                few_shot=pack.prompt.few_shot,
                text_window_chars=pack.prompt.text_window_chars,
            ),
            extractor_model=pack.models.extractor,
            ask_model=pack.models.ask,
            accepted_extensions=list(pack.inbox.accepted_extensions),
        )


class ProjectDetail(BaseModel):
    """Full project view used after opening one — paths, pack, approval."""

    name: str
    label: str
    project_dir: str
    vault_dir: str
    inbox_dir: str
    sources_dir: str
    has_inbox: bool
    schema_ttl: str | None
    sparql_dir: str | None
    approval_backend: str
    pack: DomainPackOut

    @classmethod
    def from_project(cls, project: Project) -> "ProjectDetail":
        return cls(
            name=project.name,
            label=project.label,
            project_dir=str(project.project_dir),
            vault_dir=str(project.vault_dir),
            inbox_dir=str(project.inbox_dir),
            sources_dir=str(project.sources_dir),
            has_inbox=project.has_inbox,
            schema_ttl=str(project.schema_ttl) if project.schema_ttl else None,
            sparql_dir=str(project.sparql_dir) if project.sparql_dir else None,
            approval_backend=project.approval_config.get("backend", "filesystem"),
            pack=DomainPackOut.from_pack(project.pack),
        )


class ProjectCreateIn(BaseModel):
    """Request body for ``POST /api/projects``."""

    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="snake_case identifier; becomes the projects/<name>/ folder",
    )
    label: str | None = None
    template: str = "compliance"
    backend: Literal["filesystem", "git"] = "filesystem"


class PackTemplateOut(BaseModel):
    """Built-in pack templates available to ``POST /api/projects``."""

    name: str
    label: str
    description: str | None = None
