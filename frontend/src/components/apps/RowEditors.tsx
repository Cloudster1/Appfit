import { ActionIcon, Autocomplete, Button, Group, Select, Stack, TextInput } from "@mantine/core";
import type { UseFormReturnType } from "@mantine/form";
import { IconPlus, IconTrash } from "@tabler/icons-react";

import { useMaintainers } from "../../api/hooks";
import { ICON_SIZE } from "../../config";
import type { AppFormValues, LinkRow, MaintainerRow } from "./formModel";

type FormProp = { form: UseFormReturnType<AppFormValues> };

const ROLE_OPTIONS = ["owner", "maintainer", "contact"];
const KIND_OPTIONS = ["person", "team"];
const NARROW_SELECT = 130;

export function MaintainersEditor({ form }: FormProp) {
  const maintainers = useMaintainers();
  const known = maintainers.data ?? [];

  return (
    <Stack gap="xs">
      {form.values.maintainers.map((_, i) => (
        <Group key={i} gap="xs" wrap="nowrap" align="flex-start">
          <Autocomplete
            style={{ flex: 2 }}
            placeholder="Name"
            aria-label={`Maintainer ${i + 1} name`}
            data={[...new Set(known.map((m) => m.name))]}
            {...form.getInputProps(`maintainers.${i}.name`)}
            onOptionSubmit={(name) => {
              const match = known.find((m) => m.name === name);
              if (match) {
                form.setFieldValue(`maintainers.${i}.email`, match.email ?? "");
                form.setFieldValue(`maintainers.${i}.kind`, match.kind);
                form.setFieldValue(`maintainers.${i}.org_unit`, match.org_unit ?? "");
              }
            }}
          />
          <TextInput
            style={{ flex: 2 }}
            placeholder="Email"
            aria-label={`Maintainer ${i + 1} email`}
            {...form.getInputProps(`maintainers.${i}.email`)}
          />
          <Select
            w={NARROW_SELECT}
            data={ROLE_OPTIONS}
            allowDeselect={false}
            aria-label={`Maintainer ${i + 1} role`}
            {...form.getInputProps(`maintainers.${i}.role`)}
          />
          <Select
            w={NARROW_SELECT}
            data={KIND_OPTIONS}
            allowDeselect={false}
            aria-label={`Maintainer ${i + 1} kind`}
            {...form.getInputProps(`maintainers.${i}.kind`)}
          />
          <ActionIcon
            variant="subtle"
            color="red"
            mt="xs"
            aria-label={`Remove maintainer ${i + 1}`}
            onClick={() => form.removeListItem("maintainers", i)}
          >
            <IconTrash size={ICON_SIZE.sm} />
          </ActionIcon>
        </Group>
      ))}
      <Group>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconPlus size={ICON_SIZE.sm} />}
          onClick={() =>
            form.insertListItem("maintainers", {
              name: "",
              email: "",
              role: "maintainer",
              kind: "person",
              org_unit: "",
            } satisfies MaintainerRow)
          }
        >
          Add maintainer
        </Button>
      </Group>
    </Stack>
  );
}

export function LinksEditor({ form }: FormProp) {
  return (
    <Stack gap="xs">
      {form.values.links.map((_, i) => (
        <Group key={i} gap="xs" wrap="nowrap" align="flex-start">
          <TextInput
            style={{ flex: 1 }}
            placeholder="Label"
            aria-label={`Link ${i + 1} label`}
            {...form.getInputProps(`links.${i}.label`)}
          />
          <TextInput
            style={{ flex: 3 }}
            placeholder="https://..."
            aria-label={`Link ${i + 1} URL`}
            {...form.getInputProps(`links.${i}.url`)}
          />
          <ActionIcon
            variant="subtle"
            color="red"
            mt="xs"
            aria-label={`Remove link ${i + 1}`}
            onClick={() => form.removeListItem("links", i)}
          >
            <IconTrash size={ICON_SIZE.sm} />
          </ActionIcon>
        </Group>
      ))}
      <Group>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconPlus size={ICON_SIZE.sm} />}
          onClick={() => form.insertListItem("links", { label: "", url: "" } satisfies LinkRow)}
        >
          Add link
        </Button>
      </Group>
    </Stack>
  );
}
