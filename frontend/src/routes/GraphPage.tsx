import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Divider,
  Drawer,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconNetwork } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useActiveProject } from "../state/useActiveProject";
import { useRebuildTtl, useVaultFile, useVaultGraph } from "../api/hooks";
import { GraphvizSvg } from "../components/GraphvizSvg";
import { PropertiesTable } from "../components/PropertiesTable";

export function GraphPage() {
  const { projectName, data: project } = useActiveProject();
  const [selectedCqId, setSelectedCqId] = useState<string | null>(null);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [drawerOpened, { open: openDrawer, close: closeDrawer }] =
    useDisclosure(false);

  const cqs = project?.pack.competency_questions ?? [];

  const {
    data: graphData,
    isPending: graphLoading,
    error: graphError,
  } = useVaultGraph(projectName, selectedCqId ?? undefined);

  const rebuildTtl = useRebuildTtl(projectName);

  function handleNodeClick(filename: string) {
    setSelectedFilename(filename);
    openDrawer();
  }

  const isEmpty = graphData && !graphData.dot.includes("[label=");

  return (
    <Stack>
      <Group gap="xs" align="baseline">
        <IconNetwork size={20} />
        <Title order={2}>Graph</Title>
        <Text size="sm" c="dimmed">
          Entity relationships from the approved vault.
        </Text>
      </Group>

      {cqs.length === 0 && (
        <Alert color="gray" variant="light">
          No competency questions defined in this pack.
        </Alert>
      )}

      {cqs.length > 0 && (
        <Stack gap="xs">
          <Text size="sm" fw={500}>
            Select a question to explore:
          </Text>
          <Group gap="xs">
            {cqs.map((cq) => (
              <UnstyledButton
                key={cq.id}
                onClick={() => setSelectedCqId(cq.id)}
                p="xs"
                style={{
                  borderRadius: 6,
                  background:
                    selectedCqId === cq.id
                      ? "var(--mantine-color-indigo-light)"
                      : "var(--mantine-color-default-hover)",
                  border:
                    selectedCqId === cq.id
                      ? "1px solid var(--mantine-color-indigo-4)"
                      : "1px solid transparent",
                }}
              >
                <Text size="sm" fw={selectedCqId === cq.id ? 600 : 400}>
                  {cq.label}
                </Text>
              </UnstyledButton>
            ))}
          </Group>
        </Stack>
      )}

      {!selectedCqId && cqs.length > 0 && (
        <Text size="sm" c="dimmed">
          Select a question above to render its subgraph.
        </Text>
      )}

      {selectedCqId && graphLoading && (
        <Group gap="xs">
          <Loader size="sm" />
          <Text c="dimmed" size="sm">
            Building graph…
          </Text>
        </Group>
      )}

      {selectedCqId && graphError && (
        <Alert color="red" variant="light" title="Failed to load graph">
          <Stack gap="xs">
            <Text size="sm">{(graphError as Error).message}</Text>
            <Button
              size="xs"
              variant="light"
              loading={rebuildTtl.isPending}
              onClick={() => rebuildTtl.mutate()}
            >
              Rebuild vault TTL
            </Button>
          </Stack>
        </Alert>
      )}

      {selectedCqId && isEmpty && (
        <Alert color="gray" variant="light">
          No entities matched this question.
        </Alert>
      )}

      {selectedCqId && graphData && !isEmpty && (
        <Box>
          <GraphvizSvg dot={graphData.dot} onNodeClick={handleNodeClick} />
        </Box>
      )}

      <Drawer
        opened={drawerOpened}
        onClose={closeDrawer}
        position="right"
        title="Entity detail"
        size="md"
      >
        {selectedFilename && projectName && (
          <EntityDrawer
            projectName={projectName}
            filename={selectedFilename}
            onClose={closeDrawer}
          />
        )}
      </Drawer>
    </Stack>
  );
}

function EntityDrawer({
  projectName,
  filename,
  onClose,
}: {
  projectName: string;
  filename: string;
  onClose: () => void;
}) {
  const { data, isPending, error } = useVaultFile(projectName, filename);

  if (isPending) {
    return (
      <Group gap="xs">
        <Loader size="xs" />
        <Text c="dimmed" size="sm">
          Loading…
        </Text>
      </Group>
    );
  }

  if (error) {
    return (
      <Alert color="red" variant="light" title="Entity not found">
        {(error as Error).message}
      </Alert>
    );
  }

  if (!data) return null;

  return (
    <Stack gap="md">
      <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
        {filename}
      </Text>
      <ScrollArea.Autosize mah="70vh">
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
      <Button
        component={Link}
        to={`/projects/${projectName}/vault`}
        variant="light"
        size="sm"
        onClick={onClose}
      >
        View in Vault →
      </Button>
    </Stack>
  );
}
