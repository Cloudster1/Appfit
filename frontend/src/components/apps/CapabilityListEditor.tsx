import {
  ActionIcon,
  Button,
  Group,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core";
import type { UseFormReturnType } from "@mantine/form";
import { IconArrowDown, IconArrowUp, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";

import { CAPABILITY_ATOMIC_WARN_LEN, ICON_SIZE } from "../../config";
import { atomicWarning, type AppFormValues, type CapabilityRow } from "./formModel";

const KIND_OPTIONS = [
  { value: "capability", label: "Capability" },
  { value: "feature", label: "Feature" },
  { value: "requirement", label: "Non-functional" },
];
const KIND_SELECT_WIDTH = 150;
const PASTE_MIN_ROWS = 3;

type Props = { form: UseFormReturnType<AppFormValues>; warnLen?: number };

/** Ordered list of atomic capability statements; paste several lines to add many at once. */
export function CapabilityListEditor({ form, warnLen = CAPABILITY_ATOMIC_WARN_LEN }: Props) {
  const [paste, setPaste] = useState("");
  const rows = form.values.capabilities;

  const move = (from: number, to: number) => form.reorderListItem("capabilities", { from, to });
  const addRows = (texts: string[]) =>
    texts.forEach((text) =>
      form.insertListItem("capabilities", {
        id: null,
        kind: "capability",
        text,
        details: "",
      } satisfies CapabilityRow),
    );

  return (
    <Stack gap="xs">
      {rows.length === 0 && (
        <Text size="sm" c="dimmed">
          No capabilities yet. Each capability should be one short, specific statement, for example
          &quot;Automatische Belegerkennung per OCR&quot; or &quot;Single sign-on via Microsoft Entra
          ID&quot;.
        </Text>
      )}
      {rows.map((row, i) => {
        const warning = atomicWarning(row.text, warnLen);
        return (
          <Paper key={row.id ?? `new-${i}`} withBorder p="xs">
            <Group gap="xs" wrap="nowrap" align="flex-start">
              <Select
                w={KIND_SELECT_WIDTH}
                data={KIND_OPTIONS}
                allowDeselect={false}
                aria-label={`Kind of capability ${i + 1}`}
                {...form.getInputProps(`capabilities.${i}.kind`)}
              />
              <Stack gap={0} style={{ flex: 1 }}>
                <TextInput
                  placeholder="One atomic statement"
                  aria-label={`Capability ${i + 1}`}
                  {...form.getInputProps(`capabilities.${i}.text`)}
                />
                {warning && (
                  <Text size="xs" c="orange" mt="xs">
                    {warning}
                  </Text>
                )}
              </Stack>
              <Group gap={0} wrap="nowrap">
                <Tooltip label="Move up">
                  <ActionIcon
                    variant="subtle"
                    disabled={i === 0}
                    onClick={() => move(i, i - 1)}
                    aria-label="Move up"
                  >
                    <IconArrowUp size={ICON_SIZE.sm} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Move down">
                  <ActionIcon
                    variant="subtle"
                    disabled={i === rows.length - 1}
                    onClick={() => move(i, i + 1)}
                    aria-label="Move down"
                  >
                    <IconArrowDown size={ICON_SIZE.sm} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Remove">
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    onClick={() => form.removeListItem("capabilities", i)}
                    aria-label={`Remove capability ${i + 1}`}
                  >
                    <IconTrash size={ICON_SIZE.sm} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          </Paper>
        );
      })}
      <Group align="flex-end" gap="xs">
        <Textarea
          style={{ flex: 1 }}
          label="Add capabilities"
          description="One per line; bullets are removed"
          autosize
          minRows={PASTE_MIN_ROWS}
          value={paste}
          onChange={(e) => setPaste(e.currentTarget.value)}
        />
        <Button
          variant="light"
          leftSection={<IconPlus size={ICON_SIZE.sm} />}
          disabled={!paste.trim()}
          onClick={() => {
            addRows(
              paste
                .split("\n")
                .map((l) => l.replace(/^\s*(?:[-*+]|\d+[.)])\s+/, "").trim())
                .filter(Boolean),
            );
            setPaste("");
          }}
        >
          Add
        </Button>
      </Group>
    </Stack>
  );
}
