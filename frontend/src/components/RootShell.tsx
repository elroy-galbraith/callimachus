import { AppShell, Burger, Group, NavLink, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconBook, IconFolders } from "@tabler/icons-react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { ApiKeyBanner } from "./ApiKeyBanner";

/**
 * Top-level shell shown on routes that aren't pinned to a specific
 * project (``/projects`` list, ``/help``). The per-project sidebar lives
 * in ``ProjectShell`` and only mounts under ``/projects/:projectName/*``.
 */
export function RootShell() {
  const [opened, { toggle }] = useDisclosure();
  const { pathname } = useLocation();

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 220,
        breakpoint: "sm",
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
            />
            <Title order={4}>kgforge</Title>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        <NavLink
          component={Link}
          to="/projects"
          label="Projects"
          leftSection={<IconFolders size={16} />}
          active={pathname.startsWith("/projects")}
        />
        <NavLink
          component={Link}
          to="/help"
          label="Help"
          leftSection={<IconBook size={16} />}
          active={pathname === "/help"}
        />
      </AppShell.Navbar>
      <AppShell.Main>
        <ApiKeyBanner />
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
