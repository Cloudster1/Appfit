import {
  ActionIcon,
  AppShell,
  Avatar,
  Badge,
  Burger,
  Button,
  Center,
  Group,
  Loader,
  Menu,
  NavLink,
  Text,
  Tooltip,
  UnstyledButton,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconApps,
  IconChevronDown,
  IconFileImport,
  IconLogout,
  IconMoon,
  IconServerCog,
  IconSun,
  IconTopologyStar3,
  IconUsers,
} from "@tabler/icons-react";
import { Suspense, type ComponentType } from "react";
import { Link as RouterLink, Outlet, useLocation, useNavigate } from "react-router";

import type { Role } from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { initials } from "../components/search/format";
import { APP_TITLE, GAP_TIGHT, HEADER_HEIGHT, ICON_SIZE, LOGO_SIZE, MOBILE_NAV_WIDTH } from "../config";

type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  min: Role;
  // Paths that also mark the item active, e.g. app detail pages for "Apps".
  also?: string[];
};

const NAV: NavItem[] = [
  { to: "/", label: "Apps", icon: IconApps, min: "viewer", also: ["/apps"] },
  { to: "/landscape", label: "Landscape", icon: IconTopologyStar3, min: "viewer" },
  { to: "/import", label: "Import / export", icon: IconFileImport, min: "editor" },
  { to: "/admin/users", label: "Users", icon: IconUsers, min: "admin" },
  { to: "/admin/system", label: "System", icon: IconServerCog, min: "admin" },
];

function isActive(item: NavItem, pathname: string): boolean {
  if (item.to === "/") return pathname === "/" || (item.also ?? []).some((p) => pathname.startsWith(p));
  return pathname.startsWith(item.to);
}

export function AppShellLayout() {
  const [opened, { toggle, close }] = useDisclosure();
  const { user, hasRole, logout } = useAuth();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const navigate = useNavigate();
  const location = useLocation();
  const items = NAV.filter((item) => hasRole(item.min));

  return (
    <AppShell
      header={{ height: HEADER_HEIGHT }}
      navbar={{ width: MOBILE_NAV_WIDTH, breakpoint: "sm", collapsed: { desktop: true, mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="lg" wrap="nowrap">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label="Toggle navigation"
            />
            <UnstyledButton component={RouterLink} to="/" aria-label={`${APP_TITLE} home`}>
              <Group gap="xs" wrap="nowrap">
                <img src="/favicon.svg" alt="" width={LOGO_SIZE} height={LOGO_SIZE} />
                <Text className="rb-display" fw="bold" fz="xl">
                  {APP_TITLE}
                </Text>
              </Group>
            </UnstyledButton>
            <Group gap={GAP_TIGHT} visibleFrom="sm" component="nav" aria-label="Main">
              {items.map((item) => {
                const active = isActive(item, location.pathname);
                return (
                  <Button
                    key={item.to}
                    component={RouterLink}
                    to={item.to}
                    variant={active ? "light" : "subtle"}
                    color={active ? undefined : "gray"}
                    size="sm"
                    leftSection={<item.icon size={ICON_SIZE.sm} />}
                    aria-current={active ? "page" : undefined}
                  >
                    {item.label}
                  </Button>
                );
              })}
            </Group>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <Tooltip label={colorScheme === "dark" ? "Light mode" : "Dark mode"}>
              <ActionIcon
                variant="default"
                size="lg"
                onClick={toggleColorScheme}
                aria-label="Toggle color scheme"
              >
                {colorScheme === "dark" ? <IconSun size={ICON_SIZE.md} /> : <IconMoon size={ICON_SIZE.md} />}
              </ActionIcon>
            </Tooltip>
            {user && (
              <Menu position="bottom-end" withinPortal>
                <Menu.Target>
                  <Group gap="xs" style={{ cursor: "pointer" }} data-testid="user-menu" wrap="nowrap">
                    <Avatar name={user.display_name} color="initials" size="sm" aria-hidden>
                      {initials(user.display_name)}
                    </Avatar>
                    <Text size="sm" fw="bold" visibleFrom="xs">
                      {user.display_name}
                    </Text>
                    <Badge size="sm" variant="light" visibleFrom="xs">
                      {user.role}
                    </Badge>
                    <IconChevronDown size={ICON_SIZE.xs} />
                  </Group>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>{user.email}</Menu.Label>
                  <Menu.Item
                    leftSection={<IconLogout size={ICON_SIZE.sm} />}
                    onClick={async () => {
                      await logout();
                      navigate("/login");
                    }}
                  >
                    Sign out
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            )}
          </Group>
        </Group>
      </AppShell.Header>

      {/* Phone navigation; on wider screens the links sit in the header. */}
      <AppShell.Navbar p="xs">
        {opened &&
          items.map((item) => (
            <NavLink
              key={item.to}
              component={RouterLink}
              to={item.to}
              label={item.label}
              leftSection={<item.icon size={ICON_SIZE.md} />}
              active={isActive(item, location.pathname)}
              onClick={close}
            />
          ))}
      </AppShell.Navbar>

      <AppShell.Main bg="var(--rb-ground)">
        <Suspense
          fallback={
            <Center py="xl">
              <Loader />
            </Center>
          }
        >
          <Outlet />
        </Suspense>
      </AppShell.Main>
    </AppShell>
  );
}
