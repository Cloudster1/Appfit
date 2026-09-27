import {
  Button,
  Group,
  Modal,
  SegmentedControl,
  Select,
  Stack,
  type SelectProps,
  Switch,
  TagsInput,
  Textarea,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useState } from "react";

import {
  useApps,
  useExternalSystems,
  useSaveInterface,
  type InterfaceIn,
  type InterfaceOut,
} from "../../api/hooks";
import {
  ALL_APPS_PAGE_SIZE,
  INTERFACE_FREQUENCY_LABELS,
  INTERFACE_STATUS_LABELS,
  INTERFACE_TYPE_LABELS,
} from "../../config";
import { notifyError, notifySuccess } from "../common/notify";
import { endpointOptions, fromValue, toValue, type EndpointRef } from "./endpoint";

type Values = {
  from: string | null;
  to: string | null;
  name: string;
  type: string;
  data_objects: string[];
  frequency: string | null;
  status: string;
  bidirectional: boolean;
  description: string;
};

const DESCRIPTION_ROWS = 3;

function initialValues(
  existing: InterfaceOut | null,
  defaults: Partial<Record<"from" | "to", EndpointRef>>,
): Values {
  return {
    from: toValue(existing?.from ?? defaults.from),
    to: toValue(existing?.to ?? defaults.to),
    name: existing?.name ?? "",
    type: existing?.type ?? "rest_api",
    data_objects: existing?.data_objects ?? [],
    frequency: existing?.frequency ?? null,
    status: existing?.status ?? "active",
    bidirectional: existing?.bidirectional ?? false,
    description: existing?.description ?? "",
  };
}

export function toPayload(v: Values): InterfaceIn {
  return {
    from: fromValue(v.from!),
    to: fromValue(v.to!),
    name: v.name.trim(),
    type: v.type as InterfaceIn["type"],
    data_objects: v.data_objects,
    frequency: (v.frequency || null) as InterfaceIn["frequency"],
    status: v.status as InterfaceIn["status"],
    bidirectional: v.bidirectional,
    description: v.description.trim(),
  };
}

function EndpointSelect(props: Omit<SelectProps, "data">) {
  const apps = useApps({ sort: "name", size: ALL_APPS_PAGE_SIZE });
  const systems = useExternalSystems();
  const [search, setSearch] = useState("");
  const data = endpointOptions(
    apps.data?.items ?? [],
    systems.data ?? [],
    search,
    (props.value as string) ?? null,
  );
  return (
    <Select
      searchable
      withAsterisk
      data={data}
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage="Type a name to add an external system"
      {...props}
    />
  );
}

type Props = {
  opened: boolean;
  onClose: () => void;
  existing?: InterfaceOut | null;
  defaults?: Partial<Record<"from" | "to", EndpointRef>>;
};

/** Create or edit one interface; either end can be a catalog app or an external system. */
export function InterfaceForm({ opened, onClose, existing = null, defaults = {} }: Props) {
  return (
    <Modal opened={opened} onClose={onClose} title={existing ? "Edit interface" : "Add interface"} size="lg">
      {opened && <FormBody existing={existing} defaults={defaults} onClose={onClose} />}
    </Modal>
  );
}

function FormBody({ existing, defaults, onClose }: Required<Omit<Props, "opened">>) {
  const save = useSaveInterface(existing?.id);
  const form = useForm<Values>({
    initialValues: initialValues(existing, defaults),
    validate: {
      from: (v) => (v ? null : "Choose where the data comes from"),
      to: (v, values) =>
        !v ? "Choose where the data goes" : v === values.from ? "Choose a different endpoint" : null,
      name: (v) => (v.trim() ? null : "Give the interface a name"),
    },
  });
  const submit = form.onSubmit(async (values) => {
    try {
      await save.mutateAsync(toPayload(values));
      notifySuccess(existing ? "Interface saved" : "Interface added");
      onClose();
    } catch (e) {
      notifyError(e, "The interface could not be saved");
    }
  });

  return (
    <form onSubmit={submit}>
      <Stack>
        <Group grow align="flex-start">
          <EndpointSelect label="From (provides the data)" {...form.getInputProps("from")} />
          <EndpointSelect label="To (receives the data)" {...form.getInputProps("to")} />
        </Group>
        <Switch
          label="Data flows in both directions"
          {...form.getInputProps("bidirectional", { type: "checkbox" })}
        />
        <TextInput
          label="Name"
          required
          placeholder="e.g. Posting of approved invoices"
          {...form.getInputProps("name")}
        />
        <Group grow align="flex-start">
          <Select
            label="Type"
            allowDeselect={false}
            data={Object.entries(INTERFACE_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
            {...form.getInputProps("type")}
          />
          <Select
            label="Frequency"
            clearable
            data={Object.entries(INTERFACE_FREQUENCY_LABELS).map(([value, label]) => ({ value, label }))}
            {...form.getInputProps("frequency")}
          />
        </Group>
        <TagsInput
          label="Data objects"
          placeholder="e.g. invoices, employees; press Enter after each"
          {...form.getInputProps("data_objects")}
        />
        <SegmentedControl
          aria-label="Status"
          data={Object.entries(INTERFACE_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          {...form.getInputProps("status")}
        />
        <Textarea
          label="Description"
          autosize
          minRows={DESCRIPTION_ROWS}
          {...form.getInputProps("description")}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={save.isPending}>
            {existing ? "Save" : "Add interface"}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
