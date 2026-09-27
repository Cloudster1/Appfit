import { Button, Group, Paper, SegmentedControl, Stack, Text, Textarea } from "@mantine/core";
import { IconListDetails, IconSearch } from "@tabler/icons-react";

import { HINT_MAX_WIDTH, ICON_SIZE } from "../../config";
import { RequirementEditor, type EditableRequirement } from "../search/RequirementEditor";

export type ComposerMode = "text" | "list";

const MIN_ROWS = 2;
const MAX_ROWS = 12;
const PLACEHOLDER = `Type a name or keyword to filter the catalog, or describe your use case, one requirement per line:

Must have:
- Rechnungen per OCR automatisch auslesen
- Single sign-on with Microsoft Entra ID`;

type Props = {
  text: string;
  onTextChange: (text: string) => void;
  mode: ComposerMode;
  onModeChange: (mode: ComposerMode) => void;
  requirements: EditableRequirement[];
  onRequirementsChange: (value: EditableRequirement[]) => void;
  maxRequirements: number;
  canSearch: boolean;
  searching: boolean;
  parsing: boolean;
  onSearch: () => void;
  onReview: () => void;
};

/** One input for both jobs: a single line filters the catalog, a requirement list ranks it. */
export function SearchComposer(props: Props) {
  const { text, mode, requirements, canSearch } = props;
  return (
    <Paper radius="lg" p="md" withBorder>
      <Stack gap="sm">
        <Group justify="space-between">
          <SegmentedControl
            size="xs"
            value={mode}
            onChange={(v) => props.onModeChange(v as ComposerMode)}
            data={[
              { value: "text", label: "Free text" },
              {
                value: "list",
                label: `Requirements${requirements.length ? ` (${requirements.length})` : ""}`,
              },
            ]}
          />
          {mode === "text" && (
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconListDetails size={ICON_SIZE.sm} />}
              disabled={!text.trim()}
              loading={props.parsing}
              onClick={props.onReview}
            >
              Review requirements
            </Button>
          )}
        </Group>

        {mode === "text" ? (
          <Textarea
            aria-label="Use case and requirements"
            placeholder={PLACEHOLDER}
            size="md"
            autosize
            minRows={MIN_ROWS}
            maxRows={MAX_ROWS}
            value={text}
            onChange={(e) => props.onTextChange(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && canSearch) props.onSearch();
            }}
          />
        ) : (
          <RequirementEditor
            value={requirements}
            onChange={props.onRequirementsChange}
            maxItems={props.maxRequirements}
          />
        )}

        <Group justify="space-between" align="center">
          <Text size="xs" c="dimmed" maw={HINT_MAX_WIDTH}>
            A single line filters the catalog as you type. Headers like &quot;Must have:&quot; or
            &quot;Muss:&quot; set priorities. Ctrl+Enter finds matching apps.
          </Text>
          <Button
            leftSection={<IconSearch size={ICON_SIZE.sm} />}
            disabled={!canSearch}
            loading={props.searching}
            onClick={props.onSearch}
          >
            Find matching apps
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}
