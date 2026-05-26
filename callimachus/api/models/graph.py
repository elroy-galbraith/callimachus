"""Graph viewer response models."""
from __future__ import annotations

from pydantic import BaseModel


class GraphDotOut(BaseModel):
    """Response from GET /projects/{name}/graph — a Graphviz DOT string."""

    dot: str
