import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  List,
  Modal,
  SimpleGrid,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconCircleCheck, IconClockHour4, IconEdit, IconExternalLink, IconTrash } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useApp, useDeleteApp, useSimilarApps, type AppOut } from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { EmbeddingStatusBadge, LifecycleBadge } from "../components/common/badges";
import { notifyError, notifySuccess } from "../components/common/notify";
import { QueryState } from "../components/common/QueryState";
import { AppInterfaces } from "../components/interfaces/AppInterfaces";
import { pct } from "../components/search/format";
import { ICON_SIZE } from "../config";

const KIND_TITLES: Record<string, string> = {
  capability: "Capabilities",
  requirement: "Non-functional properties",
  feature: "Features",
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed" tt="uppercase" fw="bold">
        {label}
      </Text>
      <Text size="sm" component="div">
        {children || "-"}
      </Text>
    </Stack>
  );
}

function ExternalLink({ href, label }: { href: string; label: string }) {
  return (
    <Anchor href={href} target="_blank" rel="noreferrer" size="sm">
      <Group gap="xs" component="span" wrap="nowrap">
        {label} <IconExternalLink size={ICON_SIZE.xs} />
      </Group>
    </Anchor>
  );
}

function Capabilities({ app }: { app: AppOut }) {
  const kinds = ["capability", "feature", "requirement"].filter((k) =>
    app.capabilities.some((c) => c.kind === k),
  );
  if (kinds.length === 0) return <Text c="dimmed">No capabilities recorded yet.</Text>;
  return (
    <Stack>
      {kinds.map((kind) => (
        <Stack key={kind} gap="xs">
          <Title order={5}>{KIND_TITLES[kind]}</Title>
          <List spacing="xs" size="sm" center>
            {app.capabilities
              .filter((c) => c.kind === kind)
              .map((c) => (
                <List.Item
                  key={c.id}
                  icon={
                    <Tooltip label={c.indexed ? "Indexed" : "Waiting for embedding"}>
                      <ThemeIcon size="sm" radius="xl" variant="light" color={c.indexed ? "teal" : "orange"}>
                        {c.indexed ? (
                          <IconCircleCheck size={ICON_SIZE.xs} />
                        ) : (
                          <IconClockHour4 size={ICON_SIZE.xs} />
                        )}
                      </ThemeIcon>
                    </Tooltip>
                  }
                >
                  {c.text}
                  {c.details && (
                    <Text size="xs" c="dimmed">
                      {c.details}
                    </Text>
                  )}
                </List.Item>
              ))}
          </List>
        </Stack>
      ))}
    </Stack>
  );
}

function SimilarApps({ slug }: { slug: string }) {
  const similar = useSimilarApps(slug);
  if (!similar.data?.length)
    return (
      <Text size="sm" c="dimmed">
        No similar apps found (yet).
      </Text>
    );
  return (
    <Stack gap="xs">
      {similar.data.map((s) => (
        <Group key={s.slug} justify="space-between" wrap="nowrap">
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Anchor component={Link} to={`/apps/${s.slug}`} size="sm" fw="bold">
              {s.name}
            </Anchor>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {s.short_description}
            </Text>
          </Stack>
          <Text size="xs" c="dimmed">
            {pct(s.similarity)}
          </Text>
        </Group>
      ))}
    </Stack>
  );
}

export function AppDetailPage() {
  const { slug = "" } = useParams();
  const app = useApp(slug);
  const { hasRole } = useAuth();
  const navigate = useNavigate();
  const del = useDeleteApp();
  const [confirmOpen, confirm] = useDisclosure(false);

  const remove = async () => {
    try {
      await del.mutateAsync(slug);
      notifySuccess("App deleted");
      navigate("/");
    } catch (e) {
      notifyError(e, "Delete failed");
    }
  };

  return (
    <QueryState isPending={app.isPending} error={app.error}>
      {app.data && (
        <Stack>
          <Group justify="space-between" align="flex-start">
            <Stack gap="xs">
              <Group gap="sm">
                <Title order={2}>{app.data.name}</Title>
                <LifecycleBadge status={app.data.lifecycle_status} />
                <EmbeddingStatusBadge status={app.data.embedding_status} />
              </Group>
              <Text c="dimmed">{app.data.short_description}</Text>
            </Stack>
            <Group gap="xs">
              {hasRole("editor") && (
                <Button
                  component={Link}
                  to={`/apps/${slug}/edit`}
                  variant="light"
                  leftSection={<IconEdit size={ICON_SIZE.sm} />}
                >
                  Edit
                </Button>
              )}
              {hasRole("admin") && (
                <Button
                  variant="light"
                  color="red"
                  leftSection={<IconTrash size={ICON_SIZE.sm} />}
                  onClick={confirm.open}
                >
                  Delete
                </Button>
              )}
            </Group>
          </Group>

          <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
            <Stack style={{ gridColumn: "span 2" }}>
              <Card withBorder>
                <Stack>
                  {app.data.description && (
                    <Text style={{ whiteSpace: "pre-wrap" }}>{app.data.description}</Text>
                  )}
                  <Capabilities app={app.data} />
                </Stack>
              </Card>
              <AppInterfaces app={app.data} />
            </Stack>
            <Stack>
              <Card withBorder>
                <Stack gap="sm">
                  <Field label="Vendor">{app.data.vendor}</Field>
                  <Field label="Version">{app.data.version}</Field>
                  <Field label="License">
                    {[app.data.license, app.data.license_type].filter(Boolean).join(" / ")}
                  </Field>
                  <Field label="Maintainers">
                    {app.data.maintainers.length > 0 && (
                      <Stack gap={0}>
                        {app.data.maintainers.map((m) => (
                          <Text key={`${m.id}-${m.role}`} size="sm">
                            {m.email ? <Anchor href={`mailto:${m.email}`}>{m.name}</Anchor> : m.name}{" "}
                            <Text span c="dimmed" size="xs">
                              ({m.role}
                              {m.org_unit ? `, ${m.org_unit}` : ""})
                            </Text>
                          </Text>
                        ))}
                      </Stack>
                    )}
                  </Field>
                  <Field label="Tags">
                    {[...app.data.tags, ...app.data.domains, ...app.data.tech_stack].length > 0 && (
                      <Group gap="xs">
                        {app.data.domains.map((t) => (
                          <Badge key={`d-${t}`} size="sm" variant="light" color="grape">
                            {t}
                          </Badge>
                        ))}
                        {app.data.tags.map((t) => (
                          <Badge key={`t-${t}`} size="sm" variant="light">
                            {t}
                          </Badge>
                        ))}
                        {app.data.tech_stack.map((t) => (
                          <Badge key={`x-${t}`} size="sm" variant="outline" color="gray">
                            {t}
                          </Badge>
                        ))}
                      </Group>
                    )}
                  </Field>
                  <Field label="Links">
                    {(app.data.homepage_url ||
                      app.data.repo_url ||
                      app.data.docs_url ||
                      app.data.links.length > 0) && (
                      <Stack gap={0}>
                        {app.data.homepage_url && (
                          <ExternalLink href={app.data.homepage_url} label="Homepage" />
                        )}
                        {app.data.docs_url && <ExternalLink href={app.data.docs_url} label="Documentation" />}
                        {app.data.repo_url && <ExternalLink href={app.data.repo_url} label="Repository" />}
                        {app.data.links.map((l) => (
                          <ExternalLink key={l.url} href={l.url} label={l.label} />
                        ))}
                      </Stack>
                    )}
                  </Field>
                  {Object.keys(app.data.extra).length > 0 && (
                    <Field label="Additional attributes">
                      <Table withRowBorders={false}>
                        <Table.Tbody>
                          {Object.entries(app.data.extra).map(([k, v]) => (
                            <Table.Tr key={k}>
                              <Table.Td c="dimmed">{k}</Table.Td>
                              <Table.Td>{String(v)}</Table.Td>
                            </Table.Tr>
                          ))}
                        </Table.Tbody>
                      </Table>
                    </Field>
                  )}
                  <Field label="Last updated">{new Date(app.data.updated_at).toLocaleString()}</Field>
                </Stack>
              </Card>
              <Card withBorder>
                <Title order={5} mb="xs">
                  Similar apps
                </Title>
                <SimilarApps slug={slug} />
              </Card>
            </Stack>
          </SimpleGrid>

          <Modal opened={confirmOpen} onClose={confirm.close} title="Delete app?">
            <Stack>
              <Text size="sm">
                This permanently deletes <b>{app.data.name}</b>, its capabilities and its interfaces. Consider
                setting the lifecycle to retired instead.
              </Text>
              <Group justify="flex-end">
                <Button variant="default" onClick={confirm.close}>
                  Cancel
                </Button>
                <Button color="red" loading={del.isPending} onClick={remove}>
                  Delete
                </Button>
              </Group>
            </Stack>
          </Modal>
        </Stack>
      )}
    </QueryState>
  );
}
