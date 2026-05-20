"""Schema page request/response models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptPreviewIn(BaseModel):
    """Input for ``POST /api/projects/{name}/schema/preview``."""

    doc_id: str = Field("regression_doc", description="Sample document id")
    prompt_version: str | None = Field(
        None, description="Defaults to the pack's prompt.version"
    )
    text: str = Field(
        ...,
        description="Sample document text to splice into the {text_window} placeholder",
    )


class PromptPreviewOut(BaseModel):
    """Rendered system + user prompts as Claude would receive them."""

    system: str
    user: str


class ToolSchemaOut(BaseModel):
    """The generated ``extract_entities`` tool input schema (JSON Schema)."""

    schema_: dict[str, Any] = Field(..., alias="schema")
