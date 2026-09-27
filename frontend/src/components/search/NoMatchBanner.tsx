import { Alert, List, Text } from "@mantine/core";
import { IconMoodEmpty, IconPuzzle } from "@tabler/icons-react";

import type { ParsedRequirement } from "../../api/hooks";

type Props = { gaps: number[]; requirements: ParsedRequirement[] };

function GapList({ gaps, requirements }: Props) {
  const byIdx = new Map(requirements.map((r) => [r.idx, r.text]));
  return (
    <List size="sm" mt="xs">
      {gaps.map((i) => (
        <List.Item key={i}>{byIdx.get(i) ?? `Requirement ${i + 1}`}</List.Item>
      ))}
    </List>
  );
}

export function NoMatchBanner({ gaps, requirements }: Props) {
  return (
    <Alert
      color="orange"
      icon={<IconMoodEmpty />}
      title="No good match in the catalog"
      data-testid="no-match"
    >
      <Text size="sm">
        None of the catalogued applications covers enough of your requirements. The closest candidates are
        listed below for reference, but they are not recommended.
      </Text>
      {gaps.length > 0 && (
        <>
          <Text size="sm" mt="sm" fw="bold">
            Not covered by any app:
          </Text>
          <GapList gaps={gaps} requirements={requirements} />
        </>
      )}
    </Alert>
  );
}

export function CatalogGapsAlert({ gaps, requirements }: Props) {
  if (gaps.length === 0) return null;
  return (
    <Alert color="gray" icon={<IconPuzzle />} title="Gaps in the catalog" data-testid="catalog-gaps">
      <Text size="sm">No app in the catalog covers these requirements:</Text>
      <GapList gaps={gaps} requirements={requirements} />
    </Alert>
  );
}
