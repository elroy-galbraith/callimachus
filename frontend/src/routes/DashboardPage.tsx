import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Blockquote,
  Box,
  Button,
  Card,
  Code,
  Group,
  Loader,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconCheck,
  IconFile,
  IconFileText,
  IconInbox,
  IconPlayerPlay,
  IconTrash,
  IconUpload,
  IconX,
} from "@tabler/icons-react";

import { extractErrorDetail } from "../api/client";
import { useQueryClient } from "@tanstack/react-query";

import {
  qk,
  useApprovePending,
  useClearInbox,
  useInbox,
  useJob,
  useJobPolling,
  useKickProcess,
  useUploadInbox,
  usePending,
  useRejectPending,
  useProject,
} from "../api/hooks";
import { JobProgressDrawer } from "../components/JobProgressDrawer";
import { useActiveProject } from "../state/useActiveProject";
import type {
  EntityCardOut,
  InboxFileOut,
  PendingSubmissionOut,
  ProcessJobResult,
} from "../api/types";

export function DashboardPage() {
  const { projectName, data: project } = useActiveProject();

  return (
    <Stack>
      <Stack gap={4}>
        <Title order={2}>Dashboard</Title>
        {project && (
          <Text size="sm" c="dimmed">
            Project <Code>{project.label}</Code> · backend{" "}
            <Badge variant="light" color="indigo">
              {project.approval_backend}
            </Badge>
          </Text>
        )}
      </Stack>

      <Section
        title="1 — Drop documents"
        icon={<IconUpload size={18} />}
      >
        {projectName && <UploadSection projectName={projectName} />}
      </Section>

      <Section
        title="2 — Inbox"
        icon={<IconInbox size={18} />}
      >
        {projectName && <InboxSection projectName={projectName} />}
      </Section>

      <Section
        title="3 — Pending review"
        icon={<IconCheck size={18} />}
      >
        {projectName && <PendingSection projectName={projectName} />}
      </Section>
    </Stack>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card withBorder padding="md" radius="md">
      <Group gap="sm" mb="sm">
        <ThemeIcon variant="light" size="sm">
          {icon}
        </ThemeIcon>
        <Title order={4}>{title}</Title>
      </Group>
      {children}
    </Card>
  );
}

// ---------- Upload --------------------------------------------------------

function UploadSection({ projectName }: { projectName: string }) {
  const { data: project } = useProject(projectName);
  const upload = useUploadInbox(projectName);
  const accepted = project?.pack.accepted_extensions ?? [".pdf"];

  return (
    <Stack>
      <Dropzone
        onDrop={(files) =>
          upload.mutate(files, {
            onSuccess: (out) => {
              const saved = out.saved.length;
              const skipped = out.skipped.length;
              notifications.show({
                title: saved
                  ? `Uploaded ${saved} file${saved === 1 ? "" : "s"}`
                  : "Nothing uploaded",
                message: skipped
                  ? `Skipped ${skipped} (extension not accepted)`
                  : undefined,
                color: saved ? "green" : "yellow",
              });
            },
            onError: (e) =>
              notifications.show({
                title: "Upload failed",
                message: extractErrorDetail(e),
                color: "red",
              }),
          })
        }
        loading={upload.isPending}
        // Server validates extensions against pack.inbox.accepted_extensions;
        // the client just signals "any binary OK".
        accept={["application/octet-stream"]}
        multiple
      >
        <Group justify="center" gap="md" mih={120}>
          <Dropzone.Accept>
            <IconUpload size={32} color="var(--mantine-color-blue-6)" />
          </Dropzone.Accept>
          <Dropzone.Reject>
            <IconX size={32} color="var(--mantine-color-red-6)" />
          </Dropzone.Reject>
          <Dropzone.Idle>
            <IconUpload size={32} color="var(--mantine-color-dimmed)" />
          </Dropzone.Idle>
          <Box>
            <Text inline>Drag files here, or click to select</Text>
            <Text size="sm" c="dimmed" mt={4}>
              Accepted: <Code>{accepted.join(", ")}</Code>
            </Text>
          </Box>
        </Group>
      </Dropzone>
    </Stack>
  );
}

// ---------- Inbox list + process ------------------------------------------

function InboxSection({ projectName }: { projectName: string }) {
  const { data: inbox, isPending } = useInbox(projectName);
  const clear = useClearInbox(projectName);
  const kickProcess = useKickProcess(projectName);
  const [jobId, setJobId] = useState<string | null>(null);
  const [drawer, drawerHandlers] = useDisclosure(false);
  const job = useJob(jobId ?? undefined);
  const qc = useQueryClient();

  // Re-fetch pending + inbox once the job lands.
  useEffect(() => {
    if (!jobId || !job.data) return;
    if (job.data.status === "done" || job.data.status === "error") {
      qc.invalidateQueries({ queryKey: qk.pending(projectName) });
      qc.invalidateQueries({ queryKey: qk.inbox(projectName) });
    }
  }, [jobId, job.data, qc, projectName]);

  useJobPolling(job, jobId);

  if (isPending)
    return (
      <Group gap="sm">
        <Loader size="sm" />
        <Text c="dimmed">Reading inbox…</Text>
      </Group>
    );

  if (!inbox || inbox.files.length === 0) {
    return (
      <Alert color="gray" variant="light">
        Nothing in the inbox yet. Drop a document above to get started.
      </Alert>
    );
  }

  const result = job.data?.result as ProcessJobResult | undefined;

  return (
    <Stack>
      <Stack gap={4}>
        {inbox.files.map((f) => (
          <InboxFileRow
            key={f.name}
            file={f}
            textWindowChars={inbox.text_window_chars}
          />
        ))}
        <Text size="xs" c="dimmed" mt={6}>
          Chunk window: <Code>{inbox.text_window_chars.toLocaleString()}</Code> chars
          (from <Code>pack.yaml → prompt.text_window_chars</Code>)
        </Text>
      </Stack>
      <Group>
        <Button
          leftSection={<IconPlayerPlay size={14} />}
          loading={kickProcess.isPending}
          onClick={() =>
            kickProcess.mutate(undefined, {
              onSuccess: ({ job_id }) => {
                setJobId(job_id);
                drawerHandlers.open();
              },
              onError: (e) =>
                notifications.show({
                  title: "Process failed",
                  message: extractErrorDetail(e),
                  color: "red",
                }),
            })
          }
        >
          Process all
        </Button>
        <Button
          variant="default"
          leftSection={<IconTrash size={14} />}
          loading={clear.isPending}
          onClick={() =>
            clear.mutate(undefined, {
              onSuccess: (out) =>
                notifications.show({
                  title: "Inbox cleared",
                  message: `Deleted ${out.deleted} file${out.deleted === 1 ? "" : "s"}`,
                  color: "gray",
                }),
            })
          }
        >
          Clear inbox
        </Button>
        {jobId && (
          <Button
            variant="subtle"
            size="compact-sm"
            onClick={drawerHandlers.open}
          >
            Show progress
          </Button>
        )}
      </Group>

      {result && (
        <Alert
          color={result.failed === 0 ? "green" : "yellow"}
          title={`Last run: ${result.succeeded}/${result.processed} succeeded`}
          variant="light"
        >
          {result.failed > 0 && (
            <Stack gap={4}>
              {result.errors.map((e) => (
                <Text key={e.file} size="sm">
                  <Code>{e.file}</Code> — {e.error}
                </Text>
              ))}
            </Stack>
          )}
        </Alert>
      )}

      <JobProgressDrawer
        jobId={jobId}
        opened={drawer}
        title="Processing inbox"
        onClose={drawerHandlers.close}
      />
    </Stack>
  );
}

function InboxFileRow({
  file,
  textWindowChars,
}: {
  file: InboxFileOut;
  textWindowChars: number;
}) {
  const sizeKb = (file.size_bytes / 1024).toFixed(1);
  return (
    <Group gap="xs" wrap="nowrap">
      {file.is_text_like ? (
        <IconFileText size={14} color="var(--mantine-color-dimmed)" />
      ) : (
        <IconFile size={14} color="var(--mantine-color-dimmed)" />
      )}
      <Code style={{ flexShrink: 0 }}>{file.name}</Code>
      <Text size="sm" c="dimmed">
        {file.is_text_like && file.n_chars !== null
          ? `${file.n_chars.toLocaleString()} chars`
          : `${sizeKb} KB`}
      </Text>
      {file.n_chunks_estimate && file.n_chunks_estimate > 1 && (
        <Tooltip
          label={`Will split into ~${file.n_chunks_estimate} chunks at the ${textWindowChars.toLocaleString()}-char window`}
        >
          <Badge variant="light" color="orange">
            ~{file.n_chunks_estimate} chunks
          </Badge>
        </Tooltip>
      )}
    </Group>
  );
}

// ---------- Pending review ------------------------------------------------

function PendingSection({ projectName }: { projectName: string }) {
  const { data: pending, isPending, error } = usePending(projectName);
  if (isPending)
    return (
      <Group gap="sm">
        <Loader size="sm" />
        <Text c="dimmed">Loading pending…</Text>
      </Group>
    );
  if (error)
    return (
      <Alert color="red" title="Could not load pending submissions">
        {(error as Error).message}
      </Alert>
    );
  if (!pending || pending.length === 0)
    return (
      <Alert color="gray" variant="light">
        Nothing pending. Drop a file above and click <strong>Process all</strong> to
        populate the queue.
      </Alert>
    );
  return (
    <Stack>
      <Text size="sm" c="dimmed">
        {pending.length} submission{pending.length === 1 ? "" : "s"} awaiting review.
      </Text>
      {pending.map((sub) => (
        <PendingCard key={sub.handle} sub={sub} projectName={projectName} />
      ))}
    </Stack>
  );
}

function PendingCard({
  sub,
  projectName,
}: {
  sub: PendingSubmissionOut;
  projectName: string;
}) {
  const approve = useApprovePending(projectName);
  const reject = useRejectPending(projectName);

  return (
    <Card withBorder padding="md" radius="md">
      <Group justify="space-between" mb="sm">
        <Group gap="xs">
          <IconInbox size={16} />
          <Code>{sub.doc_id}</Code>
          <Badge variant="light" color="gray">
            {sub.backend}
          </Badge>
          <Text size="xs" c="dimmed">
            handle <Code>{sub.handle}</Code>
          </Text>
        </Group>
        <Group gap="xs">
          <Button
            color="green"
            size="xs"
            leftSection={<IconCheck size={12} />}
            loading={approve.isPending}
            onClick={() =>
              approve.mutate(sub.handle, {
                onSuccess: () =>
                  notifications.show({
                    title: "Approved",
                    message: sub.doc_id,
                    color: "green",
                  }),
                onError: (e) =>
                  notifications.show({
                    title: "Approve failed",
                    message: extractErrorDetail(e),
                    color: "red",
                  }),
              })
            }
          >
            Approve
          </Button>
          <Button
            color="red"
            variant="light"
            size="xs"
            leftSection={<IconX size={12} />}
            loading={reject.isPending}
            onClick={() =>
              reject.mutate(
                { handle: sub.handle },
                {
                  onSuccess: () =>
                    notifications.show({
                      title: "Rejected",
                      message: sub.doc_id,
                      color: "yellow",
                    }),
                  onError: (e) =>
                    notifications.show({
                      title: "Reject failed",
                      message: extractErrorDetail(e),
                      color: "red",
                    }),
                },
              )
            }
          >
            Reject
          </Button>
        </Group>
      </Group>
      <Text size="xs" c="dimmed" mb="sm">
        {sub.entities.length} entit{sub.entities.length === 1 ? "y" : "ies"}
      </Text>
      <Stack gap="xs">
        {sub.entities.map((ent) => (
          <EntityCardView key={ent.filename} entity={ent} />
        ))}
      </Stack>
    </Card>
  );
}

function EntityCardView({ entity }: { entity: EntityCardOut }) {
  const propEntries = Object.entries(entity.properties ?? {});
  return (
    <Card withBorder padding="sm" radius="sm" bg="var(--mantine-color-default-hover)">
      <Group gap="xs" mb={4}>
        {entity.cls && (
          <Badge variant="filled" color="indigo" size="sm">
            {entity.cls}
          </Badge>
        )}
        <Text fw={600} size="sm">
          {entity.label ?? entity.filename}
        </Text>
        {entity.source_section && (
          <Text size="xs" c="dimmed">
            · {entity.source_section}
          </Text>
        )}
        {entity.source_page !== null && entity.source_page !== undefined && (
          <Text size="xs" c="dimmed">
            · page {entity.source_page}
          </Text>
        )}
      </Group>
      {entity.source_text && (
        <Blockquote color="gray" iconSize={16} p="xs" m={0} mb={6}>
          <Text size="sm">{entity.source_text}</Text>
        </Blockquote>
      )}
      {propEntries.length > 0 && (
        <Text size="xs" c="dimmed">
          {propEntries
            .map(([k, v]) => `${k} → ${formatPropValue(v)}`)
            .join(" · ")}
        </Text>
      )}
      <Text size="xs" c="dimmed" mt={4}>
        <Code>{entity.filename}</Code>
      </Text>
    </Card>
  );
}

// ---------- helpers -------------------------------------------------------

function formatPropValue(v: unknown): string {
  if (Array.isArray(v)) return `[${v.join(", ")}]`;
  if (typeof v === "object" && v !== null) return JSON.stringify(v);
  return String(v);
}

