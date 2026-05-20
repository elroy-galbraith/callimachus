"""Pydantic request/response models for the kgforge HTTP API.

Convention: ``*Out`` for response bodies, ``*In`` for request bodies.
Engine dataclasses are wrapped (not re-exposed) so we can drop private
fields (e.g. ``DomainPack.pack_dir``, ``hooks_module``) and keep the wire
shape stable across engine refactors.
"""
from kgforge.api.models.project import (
    ProjectSummary,
    ProjectDetail,
    ProjectCreateIn,
    DomainPackOut,
    EntityClassOut,
    EntityPropertyOut,
    CompetencyQuestionOut,
    PromptSpecOut,
    PackTemplateOut,
)
from kgforge.api.models.job import JobStateOut, JobEventOut
from kgforge.api.models.inbox import (
    InboxClearOut,
    InboxFileOut,
    InboxListOut,
    InboxUploadOut,
)
from kgforge.api.models.pending import (
    EntityCardOut,
    PendingSubmissionOut,
    RejectIn,
)
from kgforge.api.models.proposal import (
    ApplyJobResultOut,
    ApplyResultOut,
    ConsolidatorJobResultOut,
    ProposalListOut,
    ProposalOut,
    ProposalStatusIn,
)
from kgforge.api.models.query import (
    AskResultOut,
    CqRunResult,
    GraphResultOut,
    NLAnswerOut,
    NLQueryIn,
    SelectResultOut,
    SparqlQueryIn,
    SparqlResultOut,
    VaultTtlOut,
)
from kgforge.api.models.schema import (
    PromptPreviewIn,
    PromptPreviewOut,
    ToolSchemaOut,
)
from kgforge.api.models.settings import SettingsOut

__all__ = [
    "ProjectSummary",
    "ProjectDetail",
    "ProjectCreateIn",
    "DomainPackOut",
    "EntityClassOut",
    "EntityPropertyOut",
    "CompetencyQuestionOut",
    "PromptSpecOut",
    "PackTemplateOut",
    "JobStateOut",
    "JobEventOut",
    "InboxClearOut",
    "InboxFileOut",
    "InboxListOut",
    "InboxUploadOut",
    "EntityCardOut",
    "PendingSubmissionOut",
    "RejectIn",
    "ApplyJobResultOut",
    "ApplyResultOut",
    "ConsolidatorJobResultOut",
    "ProposalListOut",
    "ProposalOut",
    "ProposalStatusIn",
    "AskResultOut",
    "CqRunResult",
    "GraphResultOut",
    "NLAnswerOut",
    "NLQueryIn",
    "SelectResultOut",
    "SparqlQueryIn",
    "SparqlResultOut",
    "VaultTtlOut",
    "PromptPreviewIn",
    "PromptPreviewOut",
    "ToolSchemaOut",
    "SettingsOut",
]
