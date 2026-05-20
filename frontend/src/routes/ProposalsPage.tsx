import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Blockquote,
  Button,
  Card,
  Code,
  Collapse,
  Divider,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconCheck,
  IconChevronDown,
  IconChevronRight,
  IconPlayerPause,
  IconRobot,
  IconSparkles,
  IconX,
} from "@tabler/icons-react";
import { useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ApiError } from "../api/client";
import {
  qk,
  useJob,
  useKickApply,
  useKickConsolidator,
  usePatchProposal,
  useProposals,
} from "../api/hooks";
import { JobProgressDrawer } from "../components/JobProgressDrawer";
import { ProposalMiniGraph } from "../components/ProposalMiniGraph";
import { useActiveProject } from "../state/useActiveProject";
import type {
  ApplyJobResult,
  ProposalOut,
  ProposalStatus,
} from "../api/types";

// Status / operation display metadata mirrored from 7_Proposals.py.
const STATUS_META: Record<ProposalStatus, { label: string; color: string }> = {
  pending: { label: "pending", color: "yellow" },
  approved: { label: "approved", color: "green" },
  rejected: { label: "rejected", color: "red" },
  deferred: { label: "deferred", color: "gray" },
  applied: { label: "applied", color: "blue" },
};

const OP_META: Record<string, { label: string }> = {
  merge_entities: { label: "🔗 Merge entities" },
  group_codes: { label: "📚 Group codes" },
  link_hierarchy: { label: "➡ Link hierarchy" },
  rename_label: { label: "✏ Rename label" },
};

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "blue",
  medium: "violet",
  low: "gray",
};

// Order the status buckets appear in.
const STATUS_ORDER: ProposalStatus[] = [
  "pending",
  "deferred",
  "approved",
  "applied",
  "rejected",
];

export function ProposalsPage() {
  const { projectName } = useActiveProject();
  const { data, isPending, error } = useProposals(projectName);

  const [consolidatorJobId, setConsolidatorJobId] = useState<string | null>(null);
  const [applyJobId, setApplyJobId] = useState<string | null>(null);
  const [drawer, drawerHandlers] = useDisclosure(false);
  const [drawerTitle, setDrawerTitle] = useState("Job");
  const [activeJob, setActiveJob] = useState<string | null>(null);

  const consolidatorJob = useJob(consolidatorJobId ?? undefined);
  const applyJob = useJob(applyJobId ?? undefined);
  const qc = useQueryClient();

  // Poll while a job is running.
  useEffect(() => {
    const which = activeJob === "consolidator" ? consolidatorJob : applyJob;
    if (!which.data) return;
    if (which.data.status === "done" || which.data.status === "error") {
      if (projectName) qc.invalidateQueries({ queryKey: qk.proposals(projectName) });
      return;
    }
    const t = setTimeout(() => which.refetch(), 1000);
    return () => clearTimeout(t);
  }, [activeJob, consolidatorJob, applyJob, qc, projectName]);

  const kickConsolidator = useKickConsolidator(projectName);
  const kickApply = useKickApply(projectName);

  // Narrow the unknown result into the typed shape for rendering.
  const applyResult: ApplyJobResult | null =
    applyJob.data?.status === "done" && applyJob.data.result
      ? (applyJob.data.result as ApplyJobResult)
      : null;

  return (
    <Stack>
      <Stack gap={4}>
        <Title order={2}>Proposals</Title>
        <Text size="sm" c="dimmed">
          Review LLM-generated consolidation proposals. Decisions persist in the
          proposal markdown files and survive re-runs of the consolidator.
        </Text>
      </Stack>

      <Card withBorder padding="md">
        <Stack>
          <Text size="sm">
            Run the consolidator to scan the vault and propose merges, groupings,
            hierarchy links, and label rewrites. <strong>Apply approved</strong>{" "}
            mutates the vault — the underlying entity files change.
          </Text>
          <Group>
            <Button
              leftSection={<IconRobot size={14} />}
              loading={kickConsolidator.isPending}
              onClick={() =>
                kickConsolidator.mutate(undefined, {
                  onSuccess: ({ job_id }) => {
                    setConsolidatorJobId(job_id);
                    setActiveJob("consolidator");
                    setDrawerTitle("Consolidator");
                    drawerHandlers.open();
                  },
                  onError: (e) =>
                    notifications.show({
                      title: "Run failed",
                      message: extractDetail(e),
                      color: "red",
                    }),
                })
              }
            >
              Run consolidator
            </Button>
            <Button
              variant="default"
              leftSection={<IconSparkles size={14} />}
              loading={kickApply.isPending}
              disabled={(data?.counts.approved ?? 0) === 0}
              onClick={() =>
                kickApply.mutate(undefined, {
                  onSuccess: ({ job_id }) => {
                    setApplyJobId(job_id);
                    setActiveJob("apply");
                    setDrawerTitle("Apply approved");
                    drawerHandlers.open();
                  },
                  onError: (e) =>
                    notifications.show({
                      title: "Apply failed",
                      message: extractDetail(e),
                      color: "red",
                    }),
                })
              }
            >
              Apply {data?.counts.approved ?? 0} approved
            </Button>
            {(consolidatorJobId || applyJobId) && (
              <Button
                variant="subtle"
                size="compact-sm"
                onClick={drawerHandlers.open}
              >
                Show progress
              </Button>
            )}
          </Group>

          {applyResult && <ApplyResultSummary result={applyResult} />}
        </Stack>
      </Card>

      {isPending && (
        <Group gap="sm">
          <Loader size="sm" />
          <Text c="dimmed">Loading proposals…</Text>
        </Group>
      )}
      {error && (
        <Alert color="red" title="Could not load proposals">
          {(error as Error).message}
        </Alert>
      )}

      {data && data.proposals.length === 0 && (
        <Alert color="gray" variant="light">
          No proposals yet. Click <strong>Run consolidator</strong> above (or run{" "}
          <Code>python scripts/consolidate.py --project &lt;name&gt; --write</Code>{" "}
          from the CLI) to populate the queue.
        </Alert>
      )}

      {data && data.proposals.length > 0 && (
        <Stack>
          <CountsBar counts={data.counts} />
          {STATUS_ORDER.map((status) => {
            const bucket = data.proposals.filter((p) => p.status === status);
            if (bucket.length === 0) return null;
            return (
              <ProposalsBucket
                key={status}
                status={status}
                proposals={bucket}
                projectName={projectName ?? ""}
              />
            );
          })}
        </Stack>
      )}

      <JobProgressDrawer
        jobId={
          activeJob === "consolidator"
            ? consolidatorJobId
            : activeJob === "apply"
            ? applyJobId
            : null
        }
        opened={drawer}
        title={drawerTitle}
        onClose={drawerHandlers.close}
      />
    </Stack>
  );
}

function CountsBar({ counts }: { counts: Record<string, number> }) {
  return (
    <Group gap="sm">
      {STATUS_ORDER.map((s) => (
        <Badge
          key={s}
          variant={s === "pending" ? "filled" : "light"}
          color={STATUS_META[s].color}
        >
          {counts[s] ?? 0} {STATUS_META[s].label}
        </Badge>
      ))}
    </Group>
  );
}

function ApplyResultSummary({ result }: { result: ApplyJobResult }) {
  return (
    <Alert
      color={result.failed === 0 ? "green" : "yellow"}
      title={`Applied ${result.succeeded}/${result.succeeded + result.failed}`}
      variant="light"
    >
      <Stack gap={4}>
        {result.results.map((r) => (
          <Group key={r.proposal_id} gap={6}>
            {r.ok ? (
              <IconCheck size={12} color="var(--mantine-color-green-6)" />
            ) : (
              <IconX size={12} color="var(--mantine-color-red-6)" />
            )}
            <Code>{r.operation}</Code>
            <Text size="sm">— {r.message}</Text>
          </Group>
        ))}
      </Stack>
    </Alert>
  );
}

function ProposalsBucket({
  status,
  proposals,
  projectName,
}: {
  status: ProposalStatus;
  proposals: ProposalOut[];
  projectName: string;
}) {
  return (
    <Stack gap="xs">
      <Group gap="xs">
        <Title order={4}>
          <Badge size="lg" variant="light" color={STATUS_META[status].color}>
            {STATUS_META[status].label}
          </Badge>
        </Title>
        <Text c="dimmed" size="sm">
          ({proposals.length})
        </Text>
      </Group>
      <Stack>
        {proposals.map((p) => (
          <ProposalCard key={p.proposal_id} proposal={p} projectName={projectName} />
        ))}
      </Stack>
    </Stack>
  );
}

function ProposalCard({
  proposal,
  projectName,
}: {
  proposal: ProposalOut;
  projectName: string;
}) {
  const [opened, { toggle }] = useDisclosure(proposal.status === "pending");
  const [notes, setNotes] = useState(proposal.reviewer_notes ?? "");
  const patch = usePatchProposal(projectName);
  const opMeta = OP_META[proposal.operation] ?? { label: proposal.operation };

  const setStatus = (status: ProposalStatus) =>
    patch.mutate(
      {
        proposalId: proposal.proposal_id,
        body: { status, reviewer_notes: notes || null },
      },
      {
        onSuccess: () =>
          notifications.show({
            title: `Marked ${status}`,
            message: proposal.proposal_id,
            color: STATUS_META[status].color,
          }),
        onError: (e) =>
          notifications.show({
            title: "Patch failed",
            message: extractDetail(e),
            color: "red",
          }),
      },
    );

  // Don't render mutation controls on an already-applied proposal.
  const locked = proposal.status === "applied";

  return (
    <Card withBorder padding="md" radius="md">
      <Group
        justify="space-between"
        wrap="nowrap"
        onClick={toggle}
        style={{ cursor: "pointer" }}
      >
        <Group gap="sm" wrap="nowrap">
          {opened ? (
            <IconChevronDown size={14} />
          ) : (
            <IconChevronRight size={14} />
          )}
          <Text fw={600}>{opMeta.label}</Text>
          <Badge variant="light" color={STATUS_META[proposal.status].color}>
            {STATUS_META[proposal.status].label}
          </Badge>
          <Badge
            variant="light"
            color={CONFIDENCE_COLOR[proposal.confidence] ?? "gray"}
          >
            {proposal.confidence} confidence
          </Badge>
          <Code style={{ fontSize: 11 }}>{proposal.proposal_id}</Code>
        </Group>
      </Group>

      <Collapse in={opened}>
        <Stack mt="sm">
          <div className="payload-summary" style={{ fontSize: 14 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {proposal.payload_summary}
            </ReactMarkdown>
          </div>

          {proposal.dot && <ProposalMiniGraph dot={proposal.dot} />}

          <Stack gap={4}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              Rationale
            </Text>
            <Blockquote color="gray" iconSize={16} p="xs" m={0}>
              <Text size="sm">{proposal.rationale || "(none)"}</Text>
            </Blockquote>
          </Stack>

          {proposal.evidence.length > 0 && (
            <Stack gap={4}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
                Evidence
              </Text>
              {proposal.evidence.map((quote, i) => (
                <Blockquote key={i} color="gray" iconSize={16} p="xs" m={0}>
                  <Text size="sm">{quote}</Text>
                </Blockquote>
              ))}
            </Stack>
          )}

          {!locked && (
            <Textarea
              label="Reviewer notes (optional)"
              autosize
              minRows={2}
              maxRows={5}
              value={notes}
              onChange={(e) => setNotes(e.currentTarget.value)}
            />
          )}

          <Divider />

          <Group justify="space-between" align="center">
            <Text size="xs" c="dimmed">
              <Code>{proposal.filename}</Code>
            </Text>
            {!locked ? (
              <Group gap="xs">
                <Button
                  color="green"
                  size="xs"
                  leftSection={<IconCheck size={12} />}
                  loading={patch.isPending}
                  onClick={() => setStatus("approved")}
                >
                  Approve
                </Button>
                <Button
                  color="red"
                  variant="light"
                  size="xs"
                  leftSection={<IconX size={12} />}
                  loading={patch.isPending}
                  onClick={() => setStatus("rejected")}
                >
                  Reject
                </Button>
                <Button
                  variant="default"
                  size="xs"
                  leftSection={<IconPlayerPause size={12} />}
                  loading={patch.isPending}
                  onClick={() => setStatus("deferred")}
                >
                  Defer
                </Button>
              </Group>
            ) : (
              <Badge color="blue" variant="light">
                Already applied to vault
              </Badge>
            )}
          </Group>
        </Stack>
      </Collapse>
    </Card>
  );
}

// ---------- helpers -------------------------------------------------------

function extractDetail(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in e.body) {
      return String((e.body as { detail: unknown }).detail);
    }
    return String(e.body);
  }
  return (e as Error).message;
}
