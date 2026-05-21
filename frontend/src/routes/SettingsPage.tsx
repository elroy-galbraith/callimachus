import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";

import { useClearCaches, useSettings } from "../api/hooks";
import { useActiveProject } from "../state/useActiveProject";

export function SettingsPage() {
  const { data: settings } = useSettings();
  const { data: project } = useActiveProject();
  const clear = useClearCaches();

  return (
    <Stack>
      <Title order={2}>Settings</Title>

      <Card withBorder padding="md">
        <Title order={4} mb="xs">
          LLM provider keys
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          Set the relevant environment variable in <Code>.env</Code> at the repo
          root and restart the API server. You only need a key for the providers
          you actually use — the model picker on the Schema page lets each
          project choose its own. Editing keys from the UI is intentionally not
          supported (the API process is one misconfigured{" "}
          <Code>--host 0.0.0.0</Code> away from leaking them).
        </Text>
        {settings && (
          <Table withRowBorders={false} verticalSpacing="xs">
            <Table.Tbody>
              {settings.providers.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td style={{ width: "40%" }}>
                    <Text size="sm">{p.label}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Code>{p.env_var}</Code>
                  </Table.Td>
                  <Table.Td style={{ textAlign: "right" }}>
                    <Badge
                      variant="light"
                      color={p.configured ? "green" : "gray"}
                    >
                      {p.configured ? "set" : "not set"}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
        {settings && !settings.api_key_set && (
          <Alert color="yellow" mt="sm" title="No provider key set">
            Extraction and ask jobs will fail until at least one provider key is
            configured.
          </Alert>
        )}
      </Card>

      <Card withBorder padding="md">
        <Title order={4} mb="xs">
          Paths
        </Title>
        <Table withRowBorders={false} verticalSpacing="xs">
          <Table.Tbody>
            <Table.Tr>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  Repo root
                </Text>
              </Table.Td>
              <Table.Td>
                <Code>{settings?.repo_root ?? "—"}</Code>
              </Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  Projects dir
                </Text>
              </Table.Td>
              <Table.Td>
                <Code>{settings?.projects_dir ?? "—"}</Code>
              </Table.Td>
            </Table.Tr>
            {project && (
              <>
                <Table.Tr>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      Project dir
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Code>{project.project_dir}</Code>
                  </Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      Vault
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Code>{project.vault_dir}</Code>
                  </Table.Td>
                </Table.Tr>
                <Table.Tr>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      Inbox
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Code>{project.inbox_dir}</Code>
                  </Table.Td>
                </Table.Tr>
              </>
            )}
          </Table.Tbody>
        </Table>
      </Card>

      <Card withBorder padding="md">
        <Title order={4} mb="xs">
          Caches
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          Reload the pack + project caches if you've edited <Code>pack.yaml</Code>
          on disk while the server is running.
        </Text>
        <Group>
          <Button
            variant="default"
            loading={clear.isPending}
            onClick={() =>
              clear.mutate(undefined, {
                onSuccess: () =>
                  notifications.show({
                    title: "Caches cleared",
                    message: "Pack + project caches reloaded on next access.",
                    color: "green",
                  }),
              })
            }
          >
            Reload caches
          </Button>
        </Group>
      </Card>

      <Alert color="gray" title="Model overrides live on the Schema page">
        Pick the extractor and ask/consolidator models for each project on the
        Schema page — per-project so different domains can use different vendors.
      </Alert>
    </Stack>
  );
}
