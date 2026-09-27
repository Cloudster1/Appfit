import {
  Badge,
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useDisclosure } from "@mantine/hooks";
import { IconKey, IconUserPlus } from "@tabler/icons-react";
import { useState } from "react";

import { useCreateUser, useUpdateUser, useUsers, type Role, type UserOut } from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { notifyError, notifySuccess } from "../components/common/notify";
import { QueryState } from "../components/common/QueryState";
import { ICON_SIZE, PASSWORD_MIN_LEN } from "../config";

const ROLES: Role[] = ["viewer", "editor", "admin"];
const ROLE_SELECT_WIDTH = 130;

const passwordRule = (v: string) =>
  v.length >= PASSWORD_MIN_LEN ? null : `At least ${PASSWORD_MIN_LEN} characters`;

function CreateUserModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const create = useCreateUser();
  const form = useForm({
    initialValues: { email: "", display_name: "", role: "viewer" as Role, password: "" },
    validate: {
      email: (v) => (/^[^@\s]+@[^@\s]+$/.test(v.trim()) ? null : "Valid email required"),
      display_name: (v) => (v.trim() ? null : "Name required"),
      password: passwordRule,
    },
  });
  const submit = form.onSubmit(async (values) => {
    try {
      await create.mutateAsync(values);
      notifySuccess(`User ${values.email} created`);
      form.reset();
      onClose();
    } catch (e) {
      notifyError(e, "Could not create user");
    }
  });
  return (
    <Modal opened={opened} onClose={onClose} title="New user">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Email" {...form.getInputProps("email")} />
          <TextInput label="Display name" {...form.getInputProps("display_name")} />
          <Select label="Role" data={ROLES} allowDeselect={false} {...form.getInputProps("role")} />
          <PasswordInput label="Initial password" {...form.getInputProps("password")} />
          <Group justify="flex-end">
            <Button type="submit" loading={create.isPending}>
              Create
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ user, onClose }: { user: UserOut | null; onClose: () => void }) {
  const update = useUpdateUser();
  const [password, setPassword] = useState("");
  const error = password ? passwordRule(password) : null;
  return (
    <Modal opened={Boolean(user)} onClose={onClose} title={`Reset password for ${user?.email ?? ""}`}>
      <Stack>
        <PasswordInput
          label="New password"
          value={password}
          error={error}
          onChange={(e) => setPassword(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button
            disabled={!password || Boolean(error)}
            loading={update.isPending}
            onClick={async () => {
              try {
                await update.mutateAsync({ id: user!.id, body: { password } });
                notifySuccess("Password updated");
                setPassword("");
                onClose();
              } catch (e) {
                notifyError(e, "Could not update password");
              }
            }}
          >
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function UsersPage() {
  const users = useUsers();
  const update = useUpdateUser();
  const { user: me } = useAuth();
  const [createOpen, createModal] = useDisclosure(false);
  const [resetFor, setResetFor] = useState<UserOut | null>(null);

  const patch = async (id: string, body: { role?: Role; is_active?: boolean }) => {
    try {
      await update.mutateAsync({ id, body });
    } catch (e) {
      notifyError(e, "Update failed");
    }
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Users</Title>
        <Button leftSection={<IconUserPlus size={ICON_SIZE.sm} />} onClick={createModal.open}>
          New user
        </Button>
      </Group>
      <QueryState isPending={users.isPending} error={users.error}>
        <Table striped verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>User</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Active</Table.Th>
              <Table.Th>Last login</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.data?.map((u) => {
              const self = u.id === me?.id;
              return (
                <Table.Tr key={u.id}>
                  <Table.Td>
                    <Text fw="bold" size="sm">
                      {u.display_name} {self && <Badge size="xs">you</Badge>}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {u.email}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Select
                      w={ROLE_SELECT_WIDTH}
                      data={ROLES}
                      value={u.role}
                      allowDeselect={false}
                      disabled={self}
                      aria-label={`Role of ${u.email}`}
                      onChange={(v) => v && patch(u.id, { role: v as Role })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      checked={u.is_active}
                      disabled={self}
                      aria-label={`${u.email} active`}
                      onChange={(e) => patch(u.id, { is_active: e.currentTarget.checked })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Button
                      variant="subtle"
                      size="xs"
                      leftSection={<IconKey size={ICON_SIZE.sm} />}
                      onClick={() => setResetFor(u)}
                    >
                      Reset password
                    </Button>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </QueryState>
      <CreateUserModal opened={createOpen} onClose={createModal.close} />
      <ResetPasswordModal user={resetFor} onClose={() => setResetFor(null)} />
    </Stack>
  );
}
