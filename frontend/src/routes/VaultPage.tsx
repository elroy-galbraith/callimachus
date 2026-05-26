import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Card,
  Code,
  Divider,
  Grid,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import {
  IconFileText,
  IconLayoutSidebar,
  IconSearch,
} from "@tabler/icons-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  useVaultDocument,
  useVaultDocuments,
  useVaultFile,
} from "../api/hooks";
import { useActiveProject } from "../state/useActiveProject";
import type { EntityCardOut, VaultDocumentOut } from "../api/types";
import { PropertiesTable } from "../components/PropertiesTable";

/**
 * Read-only browser for the approved vault.
 *
 * Three panes: documents → entities in that document → full markdown of the
 * selected entity. Mirrors what pointing Obsidian at ``vault/`` provides,
 * but without requiring reviewers to install Obsidian and configure a path.
 * Editing is deliberately out of scope; vault mutations go through the
 * Proposals flow.
 */
export function VaultPage() {
  const { projectName } = useActiveProject();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);

  // React Router reuses this component when the URL switches between
  // ``/projects/A/vault`` and ``/projects/B/vault`` (same route, different
  // param), so without this reset the stale selection from project A
  // would be requested against B and return 404. Mostly hit via
  // browser back/forward; the in-app nav goes through the projects index.
  useEffect(() => {
    setSelectedDocId(null);
    setSelectedFilename(null);
  }, [projectName]);

  return (
    <Stack>
      <Group gap="xs" align="baseline">
        <IconLayoutSidebar size={20} />
        <Title order={2}>Vault</Title>
        <Text size="sm" c="dimmed">
          Approved entities only — read-only. Edits happen via Proposals.
        </Text>
      </Group>

      {projectName && (
        <Grid gutter="sm">
          <Grid.Col span={{ base: 12, md: 3 }}>
            <DocumentsPane
              projectName={projectName}
              selectedDocId={selectedDocId}
              onSelect={(docId) => {
                setSelectedDocId(docId);
                setSelectedFilename(null);
              }}
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <EntitiesPane
              projectName={projectName}
              docId={selectedDocId}
              selectedFilename={selectedFilename}
              onSelect={setSelectedFilename}
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <FilePane
              projectName={projectName}
              filename={selectedFilename}
            />
          </Grid.Col>
        </Grid>
      )}
    </Stack>
  );
}

// ---------- Left pane: documents ------------------------------------------

function DocumentsPane({
  projectName,
  selectedDocId,
  onSelect,
}: {
  projectName: string;
  selectedDocId: string | null;
  onSelect: (docId: string) => void;
}) {
  const { data, isPending, error } = useVaultDocuments(projectName);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const docs = data?.documents ?? [];
    if (!filter.trim()) return docs;
    const needle = filter.toLowerCase();
    return docs.filter(
      (d) =>
        d.doc_id.toLowerCase().includes(needle) ||
        (d.source_document?.toLowerCase().includes(needle) ?? false) ||
        d.classes.some((c) => c.toLowerCase().includes(needle)),
    );
  }, [data, filter]);

  return (
    <Card withBorder radius="md" padding="sm">
      <Stack gap="xs">
        <Title order={5}>Documents</Title>
        <TextInput
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
          leftSection={<IconSearch size={14} />}
          size="xs"
        />
        {isPending && (
          <Group gap="xs">
            <Loader size="xs" />
            <Text c="dimmed" size="sm">
              Loading vault…
            </Text>
          </Group>
        )}
        {error && (
          <Alert color="red" variant="light" title="Failed to load">
            {(error as Error).message}
          </Alert>
        )}
        {data && data.documents.length === 0 && (
          <Alert color="gray" variant="light">
            Nothing approved yet. Drop a file on the Dashboard, process it, and
            approve the submission to see entities here.
          </Alert>
        )}
        {data && data.documents.length > 0 && filtered.length === 0 && (
          <Text size="sm" c="dimmed">
            No documents match <Code>{filter}</Code>.
          </Text>
        )}
        <ScrollArea.Autosize mah={520}>
          <Stack gap={4}>
            {filtered.map((doc) => (
              <DocumentRow
                key={doc.doc_id}
                doc={doc}
                active={doc.doc_id === selectedDocId}
                onClick={() => onSelect(doc.doc_id)}
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Stack>
    </Card>
  );
}

function DocumentRow({
  doc,
  active,
  onClick,
}: {
  doc: VaultDocumentOut;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <UnstyledButton
      onClick={onClick}
      p="xs"
      style={{
        borderRadius: 6,
        background: active
          ? "var(--mantine-color-indigo-light)"
          : "transparent",
      }}
    >
      <Stack gap={2}>
        <Text size="sm" fw={active ? 600 : 500} truncate>
          {doc.source_document ?? doc.doc_id}
        </Text>
        <Group gap={6}>
          <Badge variant="light" color="indigo" size="xs">
            {doc.entity_count}{" "}
            {doc.entity_count === 1 ? "entity" : "entities"}
          </Badge>
          {doc.classes.slice(0, 3).map((c) => (
            <Badge key={c} variant="default" size="xs">
              {c}
            </Badge>
          ))}
          {doc.classes.length > 3 && (
            <Text size="xs" c="dimmed">
              +{doc.classes.length - 3}
            </Text>
          )}
        </Group>
      </Stack>
    </UnstyledButton>
  );
}

// ---------- Middle pane: entities ----------------------------------------

function EntitiesPane({
  projectName,
  docId,
  selectedFilename,
  onSelect,
}: {
  projectName: string;
  docId: string | null;
  selectedFilename: string | null;
  onSelect: (filename: string) => void;
}) {
  const { data, isPending, error } = useVaultDocument(
    projectName,
    docId ?? undefined,
  );

  if (!docId) {
    return (
      <Card withBorder radius="md" padding="sm">
        <Text c="dimmed" size="sm">
          Select a document on the left to see its entities.
        </Text>
      </Card>
    );
  }

  return (
    <Card withBorder radius="md" padding="sm">
      <Stack gap="xs">
        <Title order={5}>Entities</Title>
        <Text size="xs" c="dimmed">
          <Code>{docId}</Code>
        </Text>
        {isPending && (
          <Group gap="xs">
            <Loader size="xs" />
            <Text c="dimmed" size="sm">
              Loading…
            </Text>
          </Group>
        )}
        {error && (
          <Alert color="red" variant="light" title="Failed to load">
            {(error as Error).message}
          </Alert>
        )}
        {data && (
          <ScrollArea.Autosize mah={520}>
            <Stack gap="xs">
              {data.entities.map((ent) => (
                <EntityRow
                  key={ent.filename}
                  entity={ent}
                  active={ent.filename === selectedFilename}
                  onClick={() => onSelect(ent.filename)}
                />
              ))}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Card>
  );
}

function EntityRow({
  entity,
  active,
  onClick,
}: {
  entity: EntityCardOut;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <UnstyledButton
      onClick={onClick}
      p="xs"
      style={{
        borderRadius: 6,
        background: active
          ? "var(--mantine-color-indigo-light)"
          : "var(--mantine-color-default-hover)",
      }}
    >
      <Group gap="xs" mb={4}>
        {entity.cls && (
          <Badge variant="filled" color="indigo" size="sm">
            {entity.cls}
          </Badge>
        )}
        <Text fw={600} size="sm">
          {entity.label ?? entity.filename}
        </Text>
      </Group>
      <Group gap="xs">
        {entity.source_section && (
          <Text size="xs" c="dimmed">
            {entity.source_section}
          </Text>
        )}
        {entity.source_page !== null && entity.source_page !== undefined && (
          <Text size="xs" c="dimmed">
            · page {entity.source_page}
          </Text>
        )}
      </Group>
      <Text size="xs" c="dimmed" mt={4}>
        <Code>{entity.filename}</Code>
      </Text>
    </UnstyledButton>
  );
}

// ---------- Right pane: full file ----------------------------------------

function FilePane({
  projectName,
  filename,
}: {
  projectName: string;
  filename: string | null;
}) {
  const { data, isPending, error } = useVaultFile(
    projectName,
    filename ?? undefined,
  );

  if (!filename) {
    return (
      <Card withBorder radius="md" padding="sm">
        <Text c="dimmed" size="sm">
          Select an entity to read its full markdown.
        </Text>
      </Card>
    );
  }

  return (
    <Card withBorder radius="md" padding="sm">
      <Stack gap="xs">
        <Group gap="xs" align="baseline">
          <IconFileText size={16} />
          <Title order={5} style={{ wordBreak: "break-all" }}>
            {filename}
          </Title>
        </Group>
        {isPending && (
          <Group gap="xs">
            <Loader size="xs" />
            <Text c="dimmed" size="sm">
              Loading…
            </Text>
          </Group>
        )}
        {error && (
          <Alert color="red" variant="light" title="Failed to load">
            {(error as Error).message}
          </Alert>
        )}
        {data && (
          <ScrollArea.Autosize mah={620}>
            <Stack gap="md">
              <PropertiesTable frontmatter={data.frontmatter} />
              {data.body.trim() && (
                <>
                  <Divider label="Body" />
                  <Box className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {data.body}
                    </ReactMarkdown>
                  </Box>
                </>
              )}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Card>
  );
}

