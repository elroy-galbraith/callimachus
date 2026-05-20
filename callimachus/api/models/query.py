"""Query page request/response models.

``SparqlResultOut`` is a discriminated union over the three SPARQL result
shapes the engine returns from ``ask.run_sparql``: ``select`` (variables +
row dicts), ``ask`` (bool), ``graph`` (list of stringified triples; the
engine uses ``graph`` not ``construct``).
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class SelectResultOut(BaseModel):
    kind: Literal["select"] = "select"
    variables: list[str]
    rows: list[dict[str, str | None]]


class AskResultOut(BaseModel):
    kind: Literal["ask"] = "ask"
    value: bool


class GraphResultOut(BaseModel):
    kind: Literal["graph"] = "graph"
    triples: list[str]


SparqlResultOut = Annotated[
    Union[SelectResultOut, AskResultOut, GraphResultOut],
    Field(discriminator="kind"),
]


class SparqlQueryIn(BaseModel):
    sparql: str


class VaultTtlOut(BaseModel):
    rebuilt: bool
    size_bytes: int


class CqRunResult(BaseModel):
    """What ``POST /query/competency-questions/{cq_id}/run`` returns."""

    cq_id: str
    sparql: str
    result: SparqlResultOut


class NLQueryIn(BaseModel):
    question: str
    model: str | None = Field(
        None,
        description=(
            "LiteLLM model id (e.g. anthropic/claude-sonnet-4-6, "
            "openai/gpt-4o, gemini/gemini-2.5-pro); defaults to "
            "pack.models.ask."
        ),
    )


class NLAnswerOut(BaseModel):
    """Final shape of a completed NL-ask job."""

    question: str
    sparql: str
    rationale: str
    result: SparqlResultOut
    answer: str  # markdown
