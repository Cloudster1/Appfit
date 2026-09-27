import { Box, Group, Tooltip } from "@mantine/core";

import type { ParsedRequirement, SearchResult } from "../../api/hooks";
import { GAP_TIGHT, REQUIREMENT_DOT_SIZE, STATUS_COLORS } from "../../config";
import { STATUS_TEXT } from "../search/format";

type Props = { result: SearchResult; requirements: ParsedRequirement[] };

/** One dot per requirement, in input order, colored by coverage status. */
export function RequirementDots({ result, requirements }: Props) {
  const byIdx = new Map(requirements.map((r) => [r.idx, r.text]));
  return (
    <Group gap={GAP_TIGHT} wrap="nowrap" data-testid="requirement-dots">
      {result.evidence.map((ev) => (
        <Tooltip key={ev.req_idx} label={`${byIdx.get(ev.req_idx) ?? ""}: ${STATUS_TEXT[ev.status]}`}>
          <Box
            w={REQUIREMENT_DOT_SIZE}
            h={REQUIREMENT_DOT_SIZE}
            bg={`var(--mantine-color-${STATUS_COLORS[ev.status]}-filled)`}
            style={{ borderRadius: "50%", flexShrink: 0 }}
            data-status={ev.status}
            aria-label={STATUS_TEXT[ev.status]}
          />
        </Tooltip>
      ))}
    </Group>
  );
}
