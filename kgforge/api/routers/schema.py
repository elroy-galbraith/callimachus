"""Schema router — prompt rendering + generated JSON tool schema.

The pack snapshot (classes, properties, CQ bodies) lives on
``GET /api/projects/{name}/pack`` already; this router covers the parts
of the Schema page that require *executing* engine code on input.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from kgforge.api.deps import get_project
from kgforge.api.models import (
    PromptPreviewIn,
    PromptPreviewOut,
    ToolSchemaOut,
)
from kgforge.engine import prompt as prompt_engine
from kgforge.engine import schema_builder
from kgforge.project import Project

router = APIRouter(tags=["schema"])


@router.post(
    "/projects/{name}/schema/preview",
    response_model=PromptPreviewOut,
)
def render_prompt(
    body: PromptPreviewIn,
    project: Project = Depends(get_project),
) -> PromptPreviewOut:
    """Render the system + user prompts with the provided sample text.

    Useful for confirming a pack edit before kicking off a real extraction.
    Returns 400 on missing template placeholders (e.g. the pack references
    ``{classes_block}`` but a custom template doesn't supply it).
    """
    version = body.prompt_version or project.pack.prompt.version
    try:
        system, user = prompt_engine.render_prompts(
            project.pack, body.doc_id, version, body.text
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"prompt template references missing placeholder: {exc}",
        )
    return PromptPreviewOut(system=system, user=user)


@router.get(
    "/projects/{name}/schema/tool-schema",
    response_model=ToolSchemaOut,
    response_model_by_alias=True,
)
def get_tool_schema(project: Project = Depends(get_project)) -> ToolSchemaOut:
    """The JSON Schema sent to Claude as ``extract_entities`` input_schema."""
    return ToolSchemaOut(schema=schema_builder.build_entity_schema(project.pack))
