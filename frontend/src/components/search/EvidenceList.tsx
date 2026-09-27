import { Badge, Group, Stack, Text } from "@mantine/core";
import { IconArrowRight, IconPlug } from "@tabler/icons-react";

import type { ParsedRequirement, SearchResult } from "../../api/hooks";
import { GAP_TIGHT, ICON_SIZE, PRIORITY_LABELS } from "../../config";
import { InterfaceBadges } from "../interfaces/InterfaceList";
import { interfaceText, pct } from "./format";
import { StatusIcon } from "./StatusIcon";

type Props = { result: SearchResult; requirements: ParsedRequirement[] };

/** Per requirement: status, the capability (or description) that matched, similarity and keyword hits. */
export function EvidenceList({ result, requirements }: Props) {
  const byIdx = new Map(requirements.map((r) => [r.idx, r]));
  return (
    <Stack gap="xs">
      {result.evidence.map((ev) => {
        const req = byIdx.get(ev.req_idx);
        return (
          <Group key={ev.req_idx} gap="xs" wrap="nowrap" align="flex-start" data-testid="evidence-row">
            <StatusIcon status={ev.status} />
            <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
              <Group gap="xs">
                <Text size="sm" fw="bold">
                  {req?.text ?? `Requirement ${ev.req_idx + 1}`}
                </Text>
                {req?.priority && (
                  <Badge size="xs" variant="outline" color={req.priority === "must" ? "red" : "gray"}>
                    {PRIORITY_LABELS[req.priority]}
                  </Badge>
                )}
              </Group>
              <Group gap="xs" wrap="nowrap" align="center">
                <IconArrowRight size={ICON_SIZE.xs} style={{ flexShrink: 0 }} />
                {ev.via === "interface" && ev.interface ? (
                  <Group gap={GAP_TIGHT} wrap="nowrap">
                    <IconPlug size={ICON_SIZE.xs} style={{ flexShrink: 0 }} aria-label="Interface" />
                    <Text size="sm" c="dimmed">
                      {interfaceText(ev.interface)}
                    </Text>
                    <InterfaceBadges type={ev.interface.type} status={ev.interface.status} />
                  </Group>
                ) : ev.via === "capability" && ev.capability ? (
                  <Text size="sm" c="dimmed">
                    {ev.capability.text}
                    {ev.capability.kind !== "capability" && (
                      <Badge size="xs" variant="light" ml="xs">
                        {ev.capability.kind}
                      </Badge>
                    )}
                  </Text>
                ) : ev.via === "summary" ? (
                  <Text size="sm" c="dimmed" fs="italic">
                    Related to the app description, no specific capability
                  </Text>
                ) : (
                  <Text size="sm" c="dimmed" fs="italic">
                    No evidence found
                  </Text>
                )}
              </Group>
              {ev.keyword_hits.length > 0 && (
                <Group gap="xs" mt="xs">
                  {ev.keyword_hits.map((k) => (
                    <Badge key={k} size="xs" variant="default">
                      {k}
                    </Badge>
                  ))}
                </Group>
              )}
            </Stack>
            {ev.via !== "none" && (
              <Text size="xs" c="dimmed" title="Cosine similarity" style={{ whiteSpace: "nowrap" }}>
                {pct(ev.similarity)}
              </Text>
            )}
          </Group>
        );
      })}
    </Stack>
  );
}
