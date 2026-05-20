import { useEffect, useState } from "react";
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Divider,
  Grid,
  Group,
  Loader,
  Select,
  Stack,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconBolt,
  IconMessage,
  IconRefresh,
  IconSearch,
} from "@tabler/icons-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { extractErrorDetail } from "../api/client";
import {
  useJob,
  useJobPolling,
  useKickNlAsk,
  useProjectPack,
  useRebuildTtl,
  useRunCq,
  useRunSparql,
} from "../api/hooks";
import { CodeBlock } from "../components/CodeBlock";
import { JobProgressDrawer } from "../components/JobProgressDrawer";
import { SparqlResultsTable } from "../components/SparqlResultsTable";
import { useActiveProject } from "../state/useActiveProject";
import type { NLAnswerOut } from "../api/types";

export function QueryPage() {
  const { projectName, data: project } = useActiveProject();
  const { data: pack } = useProjectPack(projectName);

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Stack gap={4}>
          <Title order={2}>Query</Title>
          {project && pack && (
            <Text size="sm" c="dimmed">
              Querying <Code>{project.label}</Code> ·{" "}
              {pack.competency_questions.length} competency question
              {pack.competency_questions.length === 1 ? "" : "s"}
            </Text>
          )}
        </Stack>
        {projectName && <RebuildTtlButton projectName={projectName} />}
      </Group>

      <Tabs defaultValue="cq">
        <Tabs.List>
          <Tabs.Tab value="cq" leftSection={<IconSearch size={14} />}>
            Competency questions
          </Tabs.Tab>
          <Tabs.Tab value="ask" leftSection={<IconMessage size={14} />}>
            Ask (natural language)
          </Tabs.Tab>
          <Tabs.Tab value="sparql" leftSection={<IconBolt size={14} />}>
            Custom SPARQL
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="cq" pt="md">
          <CQTab projectName={projectName ?? ""} />
        </Tabs.Panel>
        <Tabs.Panel value="ask" pt="md">
          <AskTab projectName={projectName ?? ""} defaultModel={pack?.ask_model} />
        </Tabs.Panel>
        <Tabs.Panel value="sparql" pt="md">
          <SparqlTab projectName={projectName ?? ""} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

function RebuildTtlButton({ projectName }: { projectName: string }) {
  const rebuild = useRebuildTtl(projectName);
  return (
    <Button
      variant="default"
      leftSection={<IconRefresh size={14} />}
      loading={rebuild.isPending}
      onClick={() =>
        rebuild.mutate(undefined, {
          onSuccess: (out) =>
            notifications.show({
              title: "vault.ttl rebuilt",
              message: `${out.size_bytes.toLocaleString()} bytes`,
              color: "green",
            }),
          onError: (e) =>
            notifications.show({
              title: "Rebuild failed",
              message: (e as Error).message,
              color: "red",
            }),
        })
      }
    >
      Rebuild vault.ttl
    </Button>
  );
}

// ---------- CQ tab --------------------------------------------------------

function CQTab({ projectName }: { projectName: string }) {
  const { data: pack } = useProjectPack(projectName);
  const runCq = useRunCq(projectName);
  const [cqId, setCqId] = useState<string | null>(null);

  if (!pack)
    return (
      <Group gap="sm">
        <Loader size="sm" />
        <Text c="dimmed">Loading…</Text>
      </Group>
    );
  if (pack.competency_questions.length === 0)
    return (
      <Alert color="blue" title="No competency questions">
        This pack ships none. Add SPARQL files alongside <Code>pack.yaml</Code> and
        register them under <Code>competency_questions</Code>.
      </Alert>
    );

  const options = pack.competency_questions.map((cq) => ({
    value: cq.id,
    label: cq.label,
  }));
  const selectedCq = pack.competency_questions.find((cq) => cq.id === cqId);

  return (
    <Stack>
      <Grid align="flex-end">
        <Grid.Col span={{ base: 12, md: 9 }}>
          <Select
            label="Question"
            data={options}
            value={cqId}
            onChange={setCqId}
            allowDeselect={false}
            searchable
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 3 }}>
          <Button
            fullWidth
            disabled={!cqId}
            loading={runCq.isPending}
            onClick={() => cqId && runCq.mutate(cqId)}
          >
            Run
          </Button>
        </Grid.Col>
      </Grid>

      {selectedCq?.sparql && (
        <Card withBorder padding="md">
          <Text size="xs" c="dimmed" mb={4}>
            SPARQL
          </Text>
          <CodeBlock maxHeight={240}>{selectedCq.sparql}</CodeBlock>
        </Card>
      )}

      {runCq.error && (
        <Alert color="red" title="Run failed">
          {(runCq.error as Error).message}
        </Alert>
      )}
      {runCq.data && (
        <Card withBorder padding="md">
          <SparqlResultsTable result={runCq.data.result} />
        </Card>
      )}
    </Stack>
  );
}

// ---------- Custom SPARQL tab --------------------------------------------

const DEFAULT_SPARQL =
  "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n" +
  "SELECT ?s ?label WHERE { ?s rdfs:label ?label } LIMIT 25";

function SparqlTab({ projectName }: { projectName: string }) {
  const [sparql, setSparql] = useState(DEFAULT_SPARQL);
  const run = useRunSparql(projectName);
  return (
    <Stack>
      <Textarea
        label="SPARQL"
        autosize
        minRows={6}
        maxRows={16}
        value={sparql}
        onChange={(e) => setSparql(e.currentTarget.value)}
        styles={{ input: { fontFamily: "ui-monospace, monospace" } }}
      />
      <Group>
        <Button
          loading={run.isPending}
          onClick={() => run.mutate({ sparql })}
        >
          Run SPARQL
        </Button>
      </Group>
      {run.error && (
        <Alert color="red" title="Query failed">
          {extractErrorDetail(run.error)}
        </Alert>
      )}
      {run.data && (
        <Card withBorder padding="md">
          <SparqlResultsTable result={run.data} />
        </Card>
      )}
    </Stack>
  );
}

// ---------- NL Ask tab ----------------------------------------------------

function AskTab({
  projectName,
  defaultModel,
}: {
  projectName: string;
  defaultModel: string | undefined;
}) {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState(defaultModel ?? "");
  useEffect(() => {
    // Project switched — refresh the default model if the user hasn't typed.
    if (defaultModel && !model) setModel(defaultModel);
  }, [defaultModel, model]);

  const kick = useKickNlAsk(projectName);
  const [jobId, setJobId] = useState<string | null>(null);
  const [drawer, drawerHandlers] = useDisclosure(false);
  const job = useJob(jobId ?? undefined);
  useJobPolling(job, jobId);

  const answer =
    job.data?.status === "done"
      ? (job.data.result as NLAnswerOut | undefined)
      : null;

  return (
    <Stack>
      <Textarea
        label="Question"
        placeholder="What does the DPA say about biometric data?"
        autosize
        minRows={2}
        maxRows={4}
        value={question}
        onChange={(e) => setQuestion(e.currentTarget.value)}
      />
      <Grid>
        <Grid.Col span={{ base: 12, md: 9 }}>
          <TextInput
            label="Model"
            description="Anthropic model id (overrides pack.models.ask)"
            value={model}
            onChange={(e) => setModel(e.currentTarget.value)}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 3 }} display="flex" style={{ alignItems: "flex-end" }}>
          <Button
            fullWidth
            disabled={!question.trim()}
            loading={kick.isPending}
            onClick={() =>
              kick.mutate(
                { question, model: model || null },
                {
                  onSuccess: ({ job_id }) => {
                    setJobId(job_id);
                    drawerHandlers.open();
                  },
                  onError: (e) =>
                    notifications.show({
                      title: "Ask failed",
                      message: extractErrorDetail(e),
                      color: "red",
                    }),
                },
              )
            }
          >
            Ask
          </Button>
        </Grid.Col>
      </Grid>

      {jobId && (
        <Group gap="xs">
          <Badge variant="light" color={badgeColor(job.data?.status)}>
            {job.data?.status ?? "queued"}
          </Badge>
          <Anchor size="sm" onClick={drawerHandlers.open}>
            Show live progress
          </Anchor>
        </Group>
      )}

      {job.data?.status === "error" && (
        <Alert color="red" title="Ask failed">
          {job.data.error ?? "unknown error"}
        </Alert>
      )}

      {answer && (
        <Stack>
          <Card withBorder padding="md">
            <Text size="xs" c="dimmed" mb={4}>
              Rationale
            </Text>
            <Text size="sm" mb="sm">
              {answer.rationale}
            </Text>
            <Divider mb="sm" />
            <Text size="xs" c="dimmed" mb={4}>
              Generated SPARQL
            </Text>
            <CodeBlock maxHeight={220}>{answer.sparql}</CodeBlock>
          </Card>
          <Card withBorder padding="md">
            <Text size="xs" c="dimmed" mb={4}>
              Intermediate result
            </Text>
            <SparqlResultsTable result={answer.result} />
          </Card>
          <Card withBorder padding="md">
            <Title order={4} mb="sm">
              Answer
            </Title>
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {answer.answer}
              </ReactMarkdown>
            </div>
          </Card>
        </Stack>
      )}

      <JobProgressDrawer
        jobId={jobId}
        opened={drawer}
        title="Ask pipeline"
        onClose={drawerHandlers.close}
      />
    </Stack>
  );
}

// ---------- helpers -------------------------------------------------------

const JOB_BADGE_COLOR: Record<string, string> = {
  done: "green",
  error: "red",
  running: "blue",
};

function badgeColor(status: string | undefined): string {
  return JOB_BADGE_COLOR[status ?? ""] ?? "gray";
}
