// Manual mirrors of the FastAPI response models.
//
// We keep these alongside `generated.ts` (produced by `npm run gen:api`)
// so the app compiles before the codegen has been run. Once the OpenAPI
// type pipeline is part of CI, components can switch to importing from
// `./generated` and these can shrink to a thin re-export.

export interface ProjectSummary {
  name: string;
  label: string;
  dir: string;
}

export interface PackTemplate {
  name: string;
  label: string;
  description: string | null;
}

export interface EntityClassOut {
  name: string;
  label: string;
  description: string | null;
  parent: string | null;
  iri: string;
}

export interface EntityPropertyOut {
  name: string;
  label: string | null;
  domain: string | null;
  range: string | null;
  datatype: boolean;
  prompt_hint: string | null;
  predicate_iri: string;
}

export interface CompetencyQuestionOut {
  id: string;
  label: string;
  file: string;
  sparql: string | null;
}

export interface PromptSpecOut {
  version: string;
  system: string;
  user: string;
  few_shot: string;
  text_window_chars: number;
}

export interface DomainPackOut {
  name: string;
  label: string;
  description: string | null;
  version: string;
  author: string | null;
  base_iri: string;
  entity_iri: string;
  prefix: string;
  entity_prefix: string;
  classes: EntityClassOut[];
  properties: EntityPropertyOut[];
  competency_questions: CompetencyQuestionOut[];
  prompt: PromptSpecOut;
  extractor_model: string;
  ask_model: string;
  accepted_extensions: string[];
}

export interface PromptPreviewIn {
  doc_id?: string;
  prompt_version?: string | null;
  text: string;
}

export interface PromptPreviewOut {
  system: string;
  user: string;
}

export interface ToolSchemaOut {
  schema: Record<string, unknown>;
}

export interface ProjectDetail {
  name: string;
  label: string;
  project_dir: string;
  vault_dir: string;
  inbox_dir: string;
  sources_dir: string;
  has_inbox: boolean;
  schema_ttl: string | null;
  sparql_dir: string | null;
  approval_backend: string;
  pack: DomainPackOut;
}

export interface ProjectCreateIn {
  name: string;
  label?: string | null;
  template: string;
  backend: "filesystem" | "git";
}

export interface ProviderStatus {
  id: string;
  label: string;
  env_var: string;
  configured: boolean;
}

export interface SettingsOut {
  api_key_set: boolean;
  providers: ProviderStatus[];
  repo_root: string;
  projects_dir: string;
}

export interface ModelsUpdateIn {
  extractor?: string | null;
  ask?: string | null;
}

// ---------- Query / SPARQL ------------------------------------------------

export interface SelectResultOut {
  kind: "select";
  variables: string[];
  rows: Array<Record<string, string | null>>;
}

export interface AskResultOut {
  kind: "ask";
  value: boolean;
}

export interface GraphResultOut {
  kind: "graph";
  triples: string[];
}

export type SparqlResultOut = SelectResultOut | AskResultOut | GraphResultOut;

export interface SparqlQueryIn {
  sparql: string;
}

export interface VaultTtlOut {
  rebuilt: boolean;
  size_bytes: number;
}

export interface CqRunResult {
  cq_id: string;
  sparql: string;
  result: SparqlResultOut;
}

export interface NLQueryIn {
  question: string;
  model?: string | null;
}

export interface NLAnswerOut {
  question: string;
  sparql: string;
  rationale: string;
  result: SparqlResultOut;
  answer: string;
}

// ---------- Jobs ----------------------------------------------------------

export interface JobEvent {
  ts: number;
  level: "info" | "warn" | "error";
  message: string;
  data?: Record<string, unknown> | null;
}

export interface JobStateOut {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error";
  progress: JobEvent[];
  result?: unknown;
  error?: string | null;
  created_at: number;
}

// ---------- Inbox / Pending -----------------------------------------------

export interface InboxFileOut {
  name: string;
  size_bytes: number;
  suffix: string;
  is_text_like: boolean;
  n_chars: number | null;
  n_chunks_estimate: number | null;
}

export interface InboxListOut {
  files: InboxFileOut[];
  accepted_extensions: string[];
  text_window_chars: number;
}

export interface InboxClearOut {
  deleted: number;
}

export interface InboxUploadOut {
  saved: InboxFileOut[];
  skipped: Array<{ name: string; reason: string }>;
}

export interface EntityCardOut {
  filename: string;
  cls: string | null;
  label: string | null;
  source_section: string | null;
  source_page: number | null;
  source_text: string | null;
  properties: Record<string, unknown>;
}

export interface PendingSubmissionOut {
  doc_id: string;
  backend: string;
  handle: string;
  review_url: string | null;
  entities: EntityCardOut[];
}

// ---------- Vault browser -------------------------------------------------

export interface VaultDocumentOut {
  doc_id: string;
  source_document: string | null;
  entity_count: number;
  classes: string[];
}

export interface VaultListOut {
  documents: VaultDocumentOut[];
}

export interface VaultDocumentDetailOut {
  doc_id: string;
  source_document: string | null;
  entities: EntityCardOut[];
}

export interface VaultFileOut {
  filename: string;
  frontmatter: Record<string, unknown>;
  body: string;
}

// ---------- Graph viewer --------------------------------------------------

export interface GraphDotOut {
  dot: string;
}

export interface ProcessJobResult {
  processed: number;
  succeeded: number;
  failed: number;
  errors: Array<{ file: string; error: string }>;
}

// ---------- Proposals -----------------------------------------------------

export type ProposalOperation =
  | "merge_entities"
  | "group_codes"
  | "link_hierarchy"
  | "rename_label";

export type ProposalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "deferred"
  | "applied";

export type ProposalConfidence = "high" | "medium" | "low";

export interface ProposalOut {
  proposal_id: string;
  operation: ProposalOperation;
  status: ProposalStatus;
  confidence: ProposalConfidence;
  payload: Record<string, unknown>;
  rationale: string;
  evidence: string[];
  reviewer_notes: string | null;
  created_at: string | null;
  model_snapshot: string | null;
  dot: string | null;
  payload_summary: string;
  filename: string;
}

export interface ProposalListOut {
  proposals: ProposalOut[];
  counts: Record<string, number>;
}

export interface ProposalStatusIn {
  status: ProposalStatus;
  reviewer_notes?: string | null;
}

export interface ApplyResultOut {
  proposal_id: string;
  operation: string;
  ok: boolean;
  message: string;
  touched: string[];
}

export interface ApplyJobResult {
  results: ApplyResultOut[];
  succeeded: number;
  failed: number;
}

export interface ConsolidatorJobResult {
  proposals_written: number;
  paths: string[];
}
