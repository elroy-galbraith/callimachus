import { useEffect } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";

import { api } from "./client";
import type {
  CqRunResult,
  DomainPackOut,
  GraphDotOut,
  InboxClearOut,
  InboxListOut,
  InboxUploadOut,
  JobStateOut,
  ModelsUpdateIn,
  NLQueryIn,
  PackTemplate,
  PendingSubmissionOut,
  ProjectCreateIn,
  ProjectDetail,
  ProjectSummary,
  ProposalListOut,
  ProposalOut,
  ProposalStatusIn,
  PromptPreviewIn,
  PromptPreviewOut,
  SettingsOut,
  SparqlQueryIn,
  SparqlResultOut,
  ToolSchemaOut,
  VaultDocumentDetailOut,
  VaultFileOut,
  VaultListOut,
  VaultTtlOut,
} from "./types";

// ---------- Query keys ------------------------------------------------------

export const qk = {
  projects: ["projects"] as const,
  project: (name: string) => ["projects", name] as const,
  projectPack: (name: string) => ["projects", name, "pack"] as const,
  toolSchema: (name: string) => ["projects", name, "schema", "tool"] as const,
  inbox: (name: string) => ["projects", name, "inbox"] as const,
  pending: (name: string) => ["projects", name, "pending"] as const,
  proposals: (name: string) => ["projects", name, "proposals"] as const,
  vault: (name: string) => ["projects", name, "vault"] as const,
  vaultDoc: (name: string, docId: string) =>
    ["projects", name, "vault", "documents", docId] as const,
  vaultFile: (name: string, filename: string) =>
    ["projects", name, "vault", "files", filename] as const,
  vaultGraph: (name: string, cqId: string) =>
    ["projects", name, "graph", cqId] as const,
  templates: ["projects", "templates"] as const,
  settings: ["settings"] as const,
};

// ---------- Projects --------------------------------------------------------

export function useProjects(opts?: Omit<UseQueryOptions<ProjectSummary[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: qk.projects,
    queryFn: () => api.get<ProjectSummary[]>("/projects"),
    ...opts,
  });
}

export function useProject(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.project(name) : ["projects", "__none__"],
    queryFn: () => api.get<ProjectDetail>(`/projects/${name}`),
    enabled: !!name,
    // Project detail (paths, pack snapshot) only changes when a user
    // edits pack.yaml on disk. Don't thrash on every nav.
    staleTime: 5 * 60_000,
  });
}

export function useProjectTemplates() {
  return useQuery({
    queryKey: qk.templates,
    queryFn: () => api.get<PackTemplate[]>("/projects/templates"),
    staleTime: 5 * 60_000,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectCreateIn) => api.post<ProjectDetail>("/projects", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.projects });
    },
  });
}

// ---------- Pack / Schema ---------------------------------------------------

export function useProjectPack(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.projectPack(name) : ["projects", "__none__", "pack"],
    queryFn: () => api.get<DomainPackOut>(`/projects/${name}/pack`),
    enabled: !!name,
    staleTime: 5 * 60_000,
  });
}

export function useToolSchema(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.toolSchema(name) : ["projects", "__none__", "schema", "tool"],
    queryFn: () => api.get<ToolSchemaOut>(`/projects/${name}/schema/tool-schema`),
    enabled: !!name,
    staleTime: 5 * 60_000,
  });
}

export function useUpdatePackModels(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ModelsUpdateIn) =>
      api.patch<DomainPackOut>(`/projects/${name}/pack/models`, body),
    onSuccess: () => {
      if (name) {
        qc.invalidateQueries({ queryKey: qk.projectPack(name) });
        qc.invalidateQueries({ queryKey: qk.project(name) });
      }
    },
  });
}

export function useRenderPrompt(name: string | undefined) {
  return useMutation({
    mutationFn: (body: PromptPreviewIn) =>
      api.post<PromptPreviewOut>(`/projects/${name}/schema/preview`, body),
  });
}

// ---------- Query -----------------------------------------------------------

export function useRebuildTtl(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<VaultTtlOut>(`/projects/${name}/query/rebuild-ttl`),
    onSuccess: () => {
      // Force the store-cache-dependent endpoints to re-fetch.
      qc.invalidateQueries({ queryKey: ["projects", name] });
    },
  });
}

export function useRunSparql(name: string | undefined) {
  return useMutation({
    mutationFn: (body: SparqlQueryIn) =>
      api.post<SparqlResultOut>(`/projects/${name}/query/sparql`, body),
  });
}

export function useRunCq(name: string | undefined) {
  return useMutation({
    mutationFn: (cqId: string) =>
      api.post<CqRunResult>(
        `/projects/${name}/query/competency-questions/${cqId}/run`,
      ),
  });
}

export function useKickNlAsk(name: string | undefined) {
  return useMutation({
    mutationFn: (body: NLQueryIn) =>
      api.post<{ job_id: string }>(`/projects/${name}/query/ask`, body),
  });
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: jobId ? ["jobs", jobId] : ["jobs", "__none__"],
    queryFn: () => api.get<JobStateOut>(`/jobs/${jobId}`),
    enabled: !!jobId,
  });
}

/**
 * Re-fetch a job's snapshot every ``intervalMs`` while it's still
 * running. The interval clears as soon as the job reaches a terminal
 * status (or the jobId becomes null). The SSE drawer is the primary
 * channel for streaming; this is the fallback for callers that just
 * need the final ``result``.
 */
export function useJobPolling(
  job: UseQueryResult<JobStateOut>,
  jobId: string | null | undefined,
  intervalMs = 1000,
): void {
  // ``job`` itself is a fresh object every render, so depending on it
  // would re-arm the timeout on every parent re-render. Narrow to the
  // bits we actually read: the status and the (stable) refetch fn.
  const status = job.data?.status;
  const { refetch } = job;
  useEffect(() => {
    if (!jobId || !status) return;
    if (status === "done" || status === "error") return;
    const t = setTimeout(() => refetch(), intervalMs);
    return () => clearTimeout(t);
  }, [jobId, status, refetch, intervalMs]);
}

// ---------- Inbox -----------------------------------------------------------

export function useInbox(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.inbox(name) : ["projects", "__none__", "inbox"],
    queryFn: () => api.get<InboxListOut>(`/projects/${name}/inbox`),
    enabled: !!name,
  });
}

export function useUploadInbox(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: FileList | File[]) =>
      api.upload<InboxUploadOut>(`/projects/${name}/inbox/upload`, files),
    onSuccess: () => {
      if (name) qc.invalidateQueries({ queryKey: qk.inbox(name) });
    },
  });
}

export function useClearInbox(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<InboxClearOut>(`/projects/${name}/inbox`),
    onSuccess: () => {
      if (name) qc.invalidateQueries({ queryKey: qk.inbox(name) });
    },
  });
}

export function useKickProcess(name: string | undefined) {
  return useMutation({
    mutationFn: () =>
      api.post<{ job_id: string }>(`/projects/${name}/inbox/process`),
  });
}

// ---------- Pending ---------------------------------------------------------

export function usePending(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.pending(name) : ["projects", "__none__", "pending"],
    queryFn: () => api.get<PendingSubmissionOut[]>(`/projects/${name}/pending`),
    enabled: !!name,
  });
}

export function useApprovePending(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (handle: string) =>
      api.post<void>(`/projects/${name}/pending/${handle}/approve`),
    onSuccess: () => {
      if (name) qc.invalidateQueries({ queryKey: qk.pending(name) });
    },
  });
}

export function useRejectPending(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { handle: string; reason?: string }) =>
      api.post<void>(`/projects/${name}/pending/${args.handle}/reject`, {
        reason: args.reason ?? "Rejected via UI",
      }),
    onSuccess: () => {
      if (name) qc.invalidateQueries({ queryKey: qk.pending(name) });
    },
  });
}

// ---------- Proposals -------------------------------------------------------

export function useProposals(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.proposals(name) : ["projects", "__none__", "proposals"],
    queryFn: () => api.get<ProposalListOut>(`/projects/${name}/proposals`),
    enabled: !!name,
  });
}

export function usePatchProposal(name: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { proposalId: string; body: ProposalStatusIn }) =>
      api.patch<ProposalOut>(
        `/projects/${name}/proposals/${args.proposalId}`,
        args.body,
      ),
    onSuccess: () => {
      if (name) qc.invalidateQueries({ queryKey: qk.proposals(name) });
    },
  });
}

export function useKickConsolidator(name: string | undefined) {
  return useMutation({
    mutationFn: () =>
      api.post<{ job_id: string }>(`/projects/${name}/proposals/run`),
  });
}

export function useKickApply(name: string | undefined) {
  return useMutation({
    mutationFn: () =>
      api.post<{ job_id: string }>(`/projects/${name}/proposals/apply`),
  });
}

// ---------- Vault browser ---------------------------------------------------

export function useVaultDocuments(name: string | undefined) {
  return useQuery({
    queryKey: name ? qk.vault(name) : ["projects", "__none__", "vault"],
    queryFn: () => api.get<VaultListOut>(`/projects/${name}/vault`),
    enabled: !!name,
  });
}

export function useVaultDocument(
  name: string | undefined,
  docId: string | undefined,
) {
  return useQuery({
    queryKey:
      name && docId
        ? qk.vaultDoc(name, docId)
        : ["projects", "__none__", "vault", "documents", "__none__"],
    queryFn: () =>
      api.get<VaultDocumentDetailOut>(
        `/projects/${name}/vault/documents/${docId}`,
      ),
    enabled: !!name && !!docId,
  });
}

export function useVaultFile(
  name: string | undefined,
  filename: string | undefined,
) {
  return useQuery({
    queryKey:
      name && filename
        ? qk.vaultFile(name, filename)
        : ["projects", "__none__", "vault", "files", "__none__"],
    queryFn: () =>
      api.get<VaultFileOut>(
        `/projects/${name}/vault/files/${encodeURIComponent(filename!)}`,
      ),
    enabled: !!name && !!filename,
  });
}

export function useVaultGraph(
  name: string | undefined,
  cqId: string | undefined,
) {
  return useQuery({
    queryKey:
      name && cqId
        ? qk.vaultGraph(name, cqId)
        : ["projects", "__none__", "graph", "__none__"],
    queryFn: () => {
      if (!name || !cqId) throw new Error("Project name and CQ id are required");
      return api.get<GraphDotOut>(
        `/projects/${name}/graph?cq=${encodeURIComponent(cqId)}`,
      );
    },
    enabled: !!name && !!cqId,
  });
}

// ---------- Settings --------------------------------------------------------

export function useSettings() {
  return useQuery({
    queryKey: qk.settings,
    queryFn: () => api.get<SettingsOut>("/settings"),
    staleTime: 60_000,
  });
}

export function useClearCaches() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ cleared: boolean }>("/settings/cache/clear"),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
}
