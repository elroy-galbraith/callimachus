import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconCirclePlus, IconFolder } from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  useCreateProject,
  useProjects,
  useProjectTemplates,
} from "../api/hooks";

export function ProjectsPage() {
  const { data: projects, isPending, error } = useProjects();
  const [opened, modal] = useDisclosure(false);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Projects</Title>
        <Button
          leftSection={<IconCirclePlus size={16} />}
          onClick={modal.open}
        >
          New project
        </Button>
      </Group>

      {isPending && (
        <Group gap="sm">
          <Loader size="sm" />
          <Text c="dimmed">Loading projects…</Text>
        </Group>
      )}
      {error && (
        <Alert color="red" title="Could not load projects">
          {(error as Error).message}
        </Alert>
      )}

      {projects && projects.length === 0 && (
        <Alert color="blue" title="No projects yet">
          Click <strong>New project</strong> above to scaffold one from a
          built-in template.
        </Alert>
      )}

      <Stack gap="sm">
        {projects?.map((p) => (
          <Card key={p.name} withBorder padding="md" radius="md">
            <Group justify="space-between" wrap="nowrap">
              <Stack gap={4}>
                <Group gap="xs">
                  <IconFolder size={16} />
                  <Anchor
                    component={Link}
                    to={`/projects/${p.name}/dashboard`}
                    fw={600}
                  >
                    {p.label}
                  </Anchor>
                  <Badge variant="light" color="gray">
                    {p.name}
                  </Badge>
                </Group>
                <Code style={{ fontSize: 11 }}>{p.dir}</Code>
              </Stack>
              <Button
                variant="subtle"
                component={Link}
                to={`/projects/${p.name}/dashboard`}
              >
                Open →
              </Button>
            </Group>
          </Card>
        ))}
      </Stack>

      <CreateProjectModal opened={opened} onClose={modal.close} />
    </Stack>
  );
}

function CreateProjectModal({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) {
  const { data: templates } = useProjectTemplates();
  const create = useCreateProject();

  const form = useForm<{
    name: string;
    label: string;
    template: string;
    backend: "filesystem" | "git";
  }>({
    initialValues: {
      name: "",
      label: "",
      template: "compliance",
      backend: "filesystem",
    },
    validate: {
      name: (v) =>
        /^[a-z][a-z0-9_]*$/.test(v)
          ? null
          : "Use snake_case: lowercase letters, digits, underscores; start with a letter.",
      template: (v) => (v ? null : "Pick a template"),
    },
  });

  const handleSubmit = form.onSubmit(async (values) => {
    try {
      await create.mutateAsync({
        name: values.name,
        label: values.label || null,
        template: values.template,
        backend: values.backend,
      });
      notifications.show({
        title: "Project created",
        message: `${values.name} is ready.`,
        color: "green",
      });
      form.reset();
      onClose();
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? typeof e.body === "object" && e.body && "detail" in e.body
            ? String((e.body as { detail: unknown }).detail)
            : String(e.body)
          : (e as Error).message;
      notifications.show({
        title: "Create failed",
        message: msg,
        color: "red",
      });
    }
  });

  const templateOptions = (templates ?? []).map((t) => ({
    value: t.name,
    label: t.label,
  }));

  return (
    <Modal opened={opened} onClose={onClose} title="New project" size="md">
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label="Name"
            description="snake_case; becomes projects/<name>/"
            placeholder="my_project"
            required
            {...form.getInputProps("name")}
          />
          <TextInput
            label="Label"
            description="Human-friendly title (optional)"
            placeholder="My Project"
            {...form.getInputProps("label")}
          />
          <Select
            label="Template"
            description="Built-in pack to scaffold from"
            data={templateOptions}
            allowDeselect={false}
            required
            {...form.getInputProps("template")}
          />
          <Select
            label="Approval backend"
            data={[
              { value: "filesystem", label: "filesystem (SQLite audit log)" },
              { value: "git", label: "git (PR branches)" },
            ]}
            allowDeselect={false}
            {...form.getInputProps("backend")}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose} type="button">
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending}>
              Create
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
