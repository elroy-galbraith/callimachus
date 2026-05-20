import {
  Alert,
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
          API key
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          Set <Code>ANTHROPIC_API_KEY</Code> in <Code>.env</Code> at the repo
          root, then restart the API server. Changing it from the UI is
          intentionally not supported — the API process is one misconfigured
          <Code>--host 0.0.0.0</Code> away from leaking the key.
        </Text>
        {settings && (
          <Text size="sm">
            Currently: <strong>{settings.api_key_set ? "set" : "not set"}</strong>
          </Text>
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

      <Alert color="gray" title="More settings land in Phase B">
        Model overrides + prompt template viewer arrive with the Schema page.
      </Alert>
    </Stack>
  );
}
