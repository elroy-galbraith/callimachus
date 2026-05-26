import {
  Alert,
  AppShell,
  Badge,
  Burger,
  Code,
  Group,
  Loader,
  NavLink,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconChartDots3,
  IconLayoutGrid,
  IconLayoutSidebar,
  IconListSearch,
  IconSchema,
  IconSettings,
} from "@tabler/icons-react";
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { useProject } from "../api/hooks";
import { ApiKeyBanner } from "./ApiKeyBanner";

const NAV: { label: string; to: string; icon: React.ReactNode }[] = [
  { label: "Dashboard", to: "dashboard", icon: <IconLayoutGrid size={16} /> },
  { label: "Schema", to: "schema", icon: <IconSchema size={16} /> },
  { label: "Vault", to: "vault", icon: <IconLayoutSidebar size={16} /> },
  { label: "Query", to: "query", icon: <IconListSearch size={16} /> },
  { label: "Proposals", to: "proposals", icon: <IconChartDots3 size={16} /> },
  { label: "Settings", to: "settings", icon: <IconSettings size={16} /> },
];

export function ProjectShell() {
  const { projectName } = useParams<{ projectName: string }>();
  const { pathname } = useLocation();
  const [opened, { toggle }] = useDisclosure();
  const { data: project, isPending, error } = useProject(projectName);

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: "sm",
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4}>Callimachus</Title>
          </Group>
          {project && (
            <Group gap="xs">
              <Text size="sm" c="dimmed">
                {project.label}
              </Text>
              <Badge variant="light" color="indigo">
                {project.approval_backend}
              </Badge>
            </Group>
          )}
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        <NavLink
          component={Link}
          to="/projects"
          label="← All projects"
          active={false}
          mb="sm"
        />
        {project && (
          <Stack gap={2} mb="sm">
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              Active
            </Text>
            <Code>{project.name}</Code>
          </Stack>
        )}
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            leftSection={item.icon}
            active={pathname.endsWith(`/${item.to}`)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <ApiKeyBanner />
        {isPending && (
          <Group gap="sm">
            <Loader size="sm" />
            <Text c="dimmed">Loading project…</Text>
          </Group>
        )}
        {error && (
          <Alert color="red" title="Could not load project">
            {(error as Error).message}
          </Alert>
        )}
        {project && <Outlet context={{ project }} />}
      </AppShell.Main>
    </AppShell>
  );
}
