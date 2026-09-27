import { Badge, Button, Drawer, Group, Stack, Text } from "@mantine/core";
import { IconArrowRight } from "@tabler/icons-react";
import { Link } from "react-router";

import type { ParsedRequirement, SearchResult } from "../../api/hooks";
import { DRAWER_WIDTH, GAP_TIGHT, ICON_SIZE, LABEL_COLORS } from "../../config";
import { LifecycleBadge } from "../common/badges";
import { EvidenceList } from "../search/EvidenceList";
import { FLAG_TEXT, LABEL_TEXT, mustHaves } from "../search/format";
import { ScoreRing } from "./Tiles";

type Props = { result: SearchResult | null; requirements: ParsedRequirement[]; onClose: () => void };

/** Why an app matched: score, flags and the evidence for every requirement. */
export function EvidenceDrawer({ result, requirements, onClose }: Props) {
  const must = result ? mustHaves(result, requirements) : null;
  return (
    <Drawer
      opened={result !== null}
      onClose={onClose}
      position="right"
      size={DRAWER_WIDTH}
      title={
        <Text className="rb-display" fw="bold" fz="xl">
          {result?.app.name}
        </Text>
      }
    >
      {result && (
        <Stack data-testid="evidence-drawer">
          <Group gap="md" wrap="nowrap">
            <ScoreRing result={result} />
            <Stack gap={GAP_TIGHT}>
              <Group gap="xs">
                <Badge color={LABEL_COLORS[result.label]} variant="light">
                  {LABEL_TEXT[result.label]}
                </Badge>
                <LifecycleBadge status={result.app.lifecycle_status} />
                {result.flags.map((f) => (
                  <Badge key={f} color="red" variant="outline">
                    {FLAG_TEXT[f] ?? f}
                  </Badge>
                ))}
              </Group>
              {must && must.total > 0 && (
                <Text size="sm" c="dimmed">
                  Covers {must.covered} of {must.total} must-haves
                </Text>
              )}
            </Stack>
          </Group>
          <Text size="sm">{result.app.short_description}</Text>
          {result.app.maintainers.length > 0 && (
            <Text size="sm" c="dimmed">
              Maintained by {result.app.maintainers.join(", ")}
            </Text>
          )}
          <Text fw={600}>Requirement by requirement</Text>
          <EvidenceList result={result} requirements={requirements} />
          <Group>
            <Button
              component={Link}
              to={`/apps/${result.app.slug}`}
              rightSection={<IconArrowRight size={ICON_SIZE.sm} />}
            >
              Open app details
            </Button>
          </Group>
        </Stack>
      )}
    </Drawer>
  );
}
