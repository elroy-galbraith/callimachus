import { useEffect, useState } from "react";
import {
  Accordion,
  Alert,
  Badge,
  Blockquote,
  Box,
  Button,
  Card,
  Code,
  Divider,
  Grid,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";

import {
  useToolSchema,
  useRenderPrompt,
  useProjectPack,
  useSettings,
  useUpdatePackModels,
} from "../api/hooks";
import { extractErrorDetail } from "../api/client";
import { CodeBlock } from "../components/CodeBlock";
import { ModelPicker } from "../components/ModelPicker";
import { useActiveProject } from "../state/useActiveProject";
import type { DomainPackOut } from "../api/types";

export function SchemaPage() {
  const { projectName } = useActiveProject();
  const { data: pack, isPending, error } = useProjectPack(projectName);
  const { data: toolSchema } = useToolSchema(projectName);

  if (isPending)
    return (
      <Group gap="sm">
        <Loader size="sm" />
        <Text c="dimmed">Loading pack…</Text>
      </Group>
    );
  if (error || !pack)
    return (
      <Alert color="red" title="Could not load pack">
        {(error as Error)?.message ?? "no data"}
      </Alert>
    );

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Title order={2}>Schema</Title>
          <Group gap="xs">
            <Code>{pack.name}</Code>
            <Badge variant="light">v{pack.version}</Badge>
            {pack.author && (
              <Text size="sm" c="dimmed">
                by {pack.author}
              </Text>
            )}
          </Group>
        </Stack>
      </Group>

      {pack.description && (
        <Blockquote color="gray" iconSize={20}>
          {pack.description}
        </Blockquote>
      )}

      <Section title="Namespaces">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NamespaceItem label="Schema IRI" value={pack.base_iri} />
          <NamespaceItem
            label="Schema prefix"
            value={`${pack.prefix}:`}
          />
          <NamespaceItem label="Entity IRI" value={pack.entity_iri} />
          <NamespaceItem
            label="Entity prefix"
            value={`${pack.entity_prefix}:`}
          />
        </SimpleGrid>
      </Section>

      <Section title={`Classes (${pack.classes.length})`}>
        <Table withTableBorder withColumnBorders striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>name</Table.Th>
              <Table.Th>label</Table.Th>
              <Table.Th>parent</Table.Th>
              <Table.Th>description</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {pack.classes.map((c) => (
              <Table.Tr key={c.name}>
                <Table.Td>
                  <Code>{c.name}</Code>
                </Table.Td>
                <Table.Td>{c.label}</Table.Td>
                <Table.Td>
                  {c.parent ? <Code>{c.parent}</Code> : <Text c="dimmed">—</Text>}
                </Table.Td>
                <Table.Td>{c.description ?? ""}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Section>

      <Section title={`Properties (${pack.properties.length})`}>
        {pack.properties.length === 0 ? (
          <Text c="dimmed" size="sm">
            This pack has no properties.
          </Text>
        ) : (
          <Table withTableBorder withColumnBorders striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>name</Table.Th>
                <Table.Th>domain</Table.Th>
                <Table.Th>range</Table.Th>
                <Table.Th>datatype?</Table.Th>
                <Table.Th>predicate IRI</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {pack.properties.map((p) => (
                <Table.Tr key={p.name}>
                  <Table.Td>
                    <Code>{p.name}</Code>
                  </Table.Td>
                  <Table.Td>{p.domain ?? "any"}</Table.Td>
                  <Table.Td>{p.range ?? "any"}</Table.Td>
                  <Table.Td>{p.datatype ? "✓" : ""}</Table.Td>
                  <Table.Td>
                    <Code>{p.predicate_iri}</Code>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Section>

      <Section
        title={`Competency questions (${pack.competency_questions.length})`}
      >
        {pack.competency_questions.length === 0 ? (
          <Text c="dimmed" size="sm">
            This pack ships no competency questions.
          </Text>
        ) : (
          <Accordion variant="separated">
            {pack.competency_questions.map((cq) => (
              <Accordion.Item key={cq.id} value={cq.id}>
                <Accordion.Control>
                  <Group gap="sm">
                    <Code>{cq.id}</Code>
                    <Text>{cq.label}</Text>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="xs">
                    <Text size="xs" c="dimmed">
                      <Code>{cq.file}</Code>
                    </Text>
                    {cq.sparql ? (
                      <CodeBlock maxHeight={300}>{cq.sparql}</CodeBlock>
                    ) : (
                      <Text c="dimmed" fs="italic">
                        (SPARQL file missing on disk)
                      </Text>
                    )}
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>
        )}
      </Section>

      <Section title="Models">
        <ModelsEditor pack={pack} />
      </Section>

      <Section title="Prompt template">
        <Text size="sm" c="dimmed" mb="sm">
          Version <Code>{pack.prompt.version}</Code>{" "}
          · text window {pack.prompt.text_window_chars.toLocaleString()} chars{" "}
          · placeholders <Code>{"{doc_id}"}</Code>, <Code>{"{prompt_version}"}</Code>,{" "}
          <Code>{"{few_shot}"}</Code>, <Code>{"{text_window}"}</Code>
        </Text>
        <PromptTabs pack={pack} />
      </Section>

      <Section title="Generated tool-use schema">
        <Text size="sm" c="dimmed" mb="sm">
          What gets sent to the LLM as the <Code>extract_entities</Code> tool's
          parameters (LiteLLM normalises this for each provider).
        </Text>
        {toolSchema ? (
          <CodeBlock maxHeight={420}>
            {JSON.stringify(toolSchema.schema, null, 2)}
          </CodeBlock>
        ) : (
          <Loader size="sm" />
        )}
      </Section>
    </Stack>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Title order={4} mb="sm">
        {title}
      </Title>
      {children}
    </Card>
  );
}

function NamespaceItem({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Code>{value}</Code>
    </Box>
  );
}

function ModelsEditor({ pack }: { pack: DomainPackOut }) {
  const { projectName } = useActiveProject();
  const { data: settings } = useSettings();
  const update = useUpdatePackModels(projectName);

  const [extractor, setExtractor] = useState(pack.extractor_model);
  const [ask, setAsk] = useState(pack.ask_model);

  // Re-sync when the underlying pack reloads (e.g. after another tab
  // saves, or the user switches projects).
  useEffect(() => {
    setExtractor(pack.extractor_model);
    setAsk(pack.ask_model);
  }, [pack.extractor_model, pack.ask_model]);

  const dirty = extractor !== pack.extractor_model || ask !== pack.ask_model;
  const errorBody = update.error ? extractErrorDetail(update.error) : null;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        Pick any LiteLLM model id (<Code>provider/model</Code>). The suggestion
        list is just a starting point — anything LiteLLM supports works.
      </Text>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <ModelPicker
          label="Extractor model"
          description="Runs on every PDF/text chunk to emit structured entities."
          value={extractor}
          onChange={setExtractor}
          providers={settings?.providers}
          disabled={update.isPending}
        />
        <ModelPicker
          label="Ask / consolidator model"
          description="Drives natural-language SPARQL synthesis and proposal consolidation."
          value={ask}
          onChange={setAsk}
          providers={settings?.providers}
          disabled={update.isPending}
        />
      </SimpleGrid>
      {errorBody && (
        <Alert color="red" title="Could not save models">
          {errorBody}
        </Alert>
      )}
      <Group>
        <Button
          loading={update.isPending}
          disabled={!dirty}
          onClick={() =>
            update.mutate(
              { extractor, ask },
              {
                onSuccess: () =>
                  notifications.show({
                    title: "Models updated",
                    message: "pack.yaml saved; new runs will use the selected models.",
                    color: "green",
                  }),
              },
            )
          }
        >
          Save
        </Button>
        <Button
          variant="default"
          disabled={!dirty || update.isPending}
          onClick={() => {
            setExtractor(pack.extractor_model);
            setAsk(pack.ask_model);
          }}
        >
          Reset
        </Button>
      </Group>
    </Stack>
  );
}

function PromptTabs({
  pack,
}: {
  pack: {
    name: string;
    prompt: {
      version: string;
      system: string;
      user: string;
      few_shot: string;
    };
  };
}) {
  const { projectName } = useActiveProject();
  const render = useRenderPrompt(projectName);
  const [docId, setDocId] = useState("regression_doc");
  const [version, setVersion] = useState(pack.prompt.version);
  const [sample, setSample] = useState(
    '§2 Interpretation. "data controller" means a person who determines the purposes …',
  );

  return (
    <Tabs defaultValue="system">
      <Tabs.List>
        <Tabs.Tab value="system">System</Tabs.Tab>
        <Tabs.Tab value="user">User</Tabs.Tab>
        <Tabs.Tab value="few-shot">Few-shot</Tabs.Tab>
        <Tabs.Tab value="preview">Live preview</Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="system" pt="sm">
        <CodeBlock maxHeight={500}>{pack.prompt.system}</CodeBlock>
      </Tabs.Panel>
      <Tabs.Panel value="user" pt="sm">
        <CodeBlock maxHeight={500}>{pack.prompt.user}</CodeBlock>
      </Tabs.Panel>
      <Tabs.Panel value="few-shot" pt="sm">
        {pack.prompt.few_shot ? (
          <CodeBlock maxHeight={500}>{pack.prompt.few_shot}</CodeBlock>
        ) : (
          <Text c="dimmed" size="sm">
            (No few-shot block configured.)
          </Text>
        )}
      </Tabs.Panel>
      <Tabs.Panel value="preview" pt="sm">
        <Stack>
          <Grid>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput
                label="Sample doc_id"
                value={docId}
                onChange={(e) => setDocId(e.currentTarget.value)}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <TextInput
                label="Sample prompt_version"
                value={version}
                onChange={(e) => setVersion(e.currentTarget.value)}
              />
            </Grid.Col>
          </Grid>
          <Textarea
            label="Sample document text"
            autosize
            minRows={4}
            maxRows={10}
            value={sample}
            onChange={(e) => setSample(e.currentTarget.value)}
          />
          <Group>
            <Button
              loading={render.isPending}
              onClick={() =>
                render.mutate({
                  doc_id: docId,
                  prompt_version: version,
                  text: sample,
                })
              }
            >
              Render
            </Button>
          </Group>
          {render.error && (
            <Alert color="red" title="Render failed">
              {extractErrorDetail(render.error)}
            </Alert>
          )}
          {render.data && (
            <Stack>
              <Divider label="Rendered system prompt" />
              <CodeBlock maxHeight={400}>{render.data.system}</CodeBlock>
              <Divider label="Rendered user prompt" />
              <CodeBlock maxHeight={500}>{render.data.user}</CodeBlock>
            </Stack>
          )}
        </Stack>
      </Tabs.Panel>
    </Tabs>
  );
}
