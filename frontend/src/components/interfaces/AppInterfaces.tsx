import { Button, Card, Center, Group, Loader, Modal, Stack, Text, Title } from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import { lazy, Suspense, useMemo, useState } from "react";

import { useDeleteInterface, useInterface, type AppOut, type InterfaceSummary } from "../../api/hooks";
import { useAuth } from "../../auth/AuthProvider";
import { ICON_SIZE } from "../../config";
import { notifyError, notifySuccess } from "../common/notify";
import { miniGraphHeight, neighbourhood } from "../graph/graphModel";
import { InterfaceForm } from "./InterfaceForm";
import { InterfaceList } from "./InterfaceList";

// React Flow and ELK load only when a graph is shown.
const LandscapeGraph = lazy(() =>
  import("../graph/LandscapeGraph").then((m) => ({ default: m.LandscapeGraph })),
);

export function GraphFallback({ height }: { height: number | string }) {
  return (
    <Center h={height}>
      <Loader />
    </Center>
  );
}

/** Interfaces card on the app page: list, one-hop graph and (for editors) add, edit and delete. */
export function AppInterfaces({ app }: { app: AppOut }) {
  const { hasRole } = useAuth();
  const canEdit = hasRole("editor");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<InterfaceSummary | null>(null);
  const editing = useInterface(editingId);
  const remove = useDeleteInterface();
  const graph = useMemo(() => neighbourhood(app), [app]);

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await remove.mutateAsync(deleting.id);
      notifySuccess("Interface deleted");
      setDeleting(null);
    } catch (e) {
      notifyError(e, "The interface could not be deleted");
    }
  };

  return (
    <Card withBorder data-testid="app-interfaces">
      <Stack>
        <Group justify="space-between">
          <Title order={4}>Interfaces</Title>
          {canEdit && (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={ICON_SIZE.sm} />}
              onClick={() => setAdding(true)}
            >
              Add interface
            </Button>
          )}
        </Group>
        {app.interfaces.length > 0 && (
          <Suspense fallback={<GraphFallback height={miniGraphHeight(graph)} />}>
            <LandscapeGraph landscape={graph} height={miniGraphHeight(graph)} compact />
          </Suspense>
        )}
        <InterfaceList
          interfaces={app.interfaces}
          onEdit={canEdit ? setEditingId : undefined}
          onDelete={canEdit ? setDeleting : undefined}
        />
      </Stack>

      <InterfaceForm
        opened={adding}
        onClose={() => setAdding(false)}
        defaults={{ from: { app: app.slug } }}
      />
      <InterfaceForm
        opened={Boolean(editingId && editing.data)}
        onClose={() => setEditingId(null)}
        existing={editing.data ?? null}
      />
      <Modal opened={deleting !== null} onClose={() => setDeleting(null)} title="Delete interface?">
        <Stack>
          <Text size="sm">
            This removes <b>{deleting?.name}</b> between {app.name} and {deleting?.counterpart.name}.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button color="red" loading={remove.isPending} onClick={confirmDelete}>
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
}
