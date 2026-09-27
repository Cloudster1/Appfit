import { ActionIcon, Button, Group, SegmentedControl, Stack, TextInput, Tooltip } from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";

import { ICON_SIZE } from "../../config";

export type Priority = "must" | "should" | "could";
export type EditableRequirement = { text: string; priority: Priority | null };

const NONE = "none";
const PRIORITY_OPTIONS = [
  { value: NONE, label: "-" },
  { value: "must", label: "Must" },
  { value: "should", label: "Should" },
  { value: "could", label: "Could" },
];

type Props = {
  value: EditableRequirement[];
  onChange: (value: EditableRequirement[]) => void;
  maxItems: number;
};

/** One row per requirement with a MoSCoW priority; "Must" gaps penalize an app's score. */
export function RequirementEditor({ value, onChange, maxItems }: Props) {
  const update = (index: number, patch: Partial<EditableRequirement>) =>
    onChange(value.map((r, i) => (i === index ? { ...r, ...patch } : r)));

  return (
    <Stack gap="xs">
      {value.map((req, i) => (
        <Group key={i} gap="xs" wrap="nowrap" align="center">
          <TextInput
            style={{ flex: 1 }}
            value={req.text}
            placeholder="Describe one requirement"
            aria-label={`Requirement ${i + 1}`}
            onChange={(e) => update(i, { text: e.currentTarget.value })}
          />
          <SegmentedControl
            size="xs"
            data={PRIORITY_OPTIONS}
            value={req.priority ?? NONE}
            aria-label={`Priority of requirement ${i + 1}`}
            onChange={(v) => update(i, { priority: v === NONE ? null : (v as Priority) })}
          />
          <Tooltip label="Remove">
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={`Remove requirement ${i + 1}`}
              onClick={() => onChange(value.filter((_, j) => j !== i))}
            >
              <IconTrash size={ICON_SIZE.sm} />
            </ActionIcon>
          </Tooltip>
        </Group>
      ))}
      <Group>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconPlus size={ICON_SIZE.sm} />}
          disabled={value.length >= maxItems}
          onClick={() => onChange([...value, { text: "", priority: null }])}
        >
          Add requirement
        </Button>
      </Group>
    </Stack>
  );
}
