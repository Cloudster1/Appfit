import { Avatar, Badge, Card, Group, List, RingProgress, Stack, Text } from "@mantine/core";
import { IconPuzzle } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import type { AppListItem, ParsedRequirement, SearchResult } from "../../api/hooks";
import {
  GAP_COMPACT,
  GAP_TIGHT,
  ICON_SIZE,
  LABEL_COLORS,
  OWNER_AVATAR_SIZE,
  PERCENT,
  TILE_AVATAR_SIZE,
  TILE_DESCRIPTION_LINES,
  TILE_MAX_TAGS,
  TILE_RING_SIZE,
  TILE_RING_THICKNESS,
} from "../../config";
import { EmbeddingStatusBadge } from "../common/badges";
import { countStatuses, FLAG_TEXT, initials, LABEL_TEXT, pct, uniqueTags } from "../search/format";
import { RequirementDots } from "./RequirementDots";

function TileHeader({ name, subtitle, aside }: { name: string; subtitle: ReactNode; aside?: ReactNode }) {
  return (
    <Group gap="sm" wrap="nowrap" align="center">
      <Avatar name={name} color="initials" variant="filled" radius="md" size={TILE_AVATAR_SIZE} aria-hidden>
        {initials(name)}
      </Avatar>
      <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
        <Text fw="bold" truncate="end">
          {name}
        </Text>
        <Text size="xs" c="dimmed" truncate="end">
          {subtitle}
        </Text>
      </Stack>
      {aside}
    </Group>
  );
}

function Owner({ name }: { name: string | undefined }) {
  if (!name) {
    return (
      <Text size="xs" c="dimmed">
        No maintainer listed
      </Text>
    );
  }
  return (
    <Group gap={GAP_COMPACT} wrap="nowrap" style={{ minWidth: 0 }}>
      <Avatar name={name} color="initials" size={OWNER_AVATAR_SIZE} aria-hidden>
        {initials(name)}
      </Avatar>
      <Text size="xs" c="dimmed" truncate="end">
        {name}
      </Text>
    </Group>
  );
}

function TileFooter({ children }: { children: ReactNode }) {
  return (
    <Group
      justify="space-between"
      wrap="nowrap"
      pt="xs"
      mt="auto"
      style={{ borderTop: "1px solid var(--rb-tile-border)" }}
    >
      {children}
    </Group>
  );
}

function subtitle(domains: string[], lifecycle: string) {
  return domains.length ? (
    <>
      {domains[0]} &middot; {lifecycle}
    </>
  ) : (
    lifecycle
  );
}

/** Catalog entry without a search: links to the app's detail page. */
export function CatalogTile({ app }: { app: AppListItem }) {
  const tags = uniqueTags(app.tags, app.tech_stack).slice(0, TILE_MAX_TAGS);
  return (
    <Card
      component={Link}
      to={`/apps/${app.slug}`}
      className="rb-tile"
      radius="lg"
      padding="md"
      data-testid="catalog-tile"
    >
      <Stack gap="sm" h="100%">
        <TileHeader
          name={app.name}
          subtitle={subtitle(app.domains, app.lifecycle_status)}
          aside={app.embedding_status === "pending" ? <EmbeddingStatusBadge status="pending" /> : undefined}
        />
        <Text size="sm" c="dimmed" lineClamp={TILE_DESCRIPTION_LINES}>
          {app.short_description}
        </Text>
        {tags.length > 0 && (
          <Group gap={GAP_TIGHT}>
            {tags.map((t) => (
              <Badge key={t} size="xs" variant="default">
                {t}
              </Badge>
            ))}
          </Group>
        )}
        <TileFooter>
          <Owner name={app.maintainers[0]} />
          <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
            {app.capability_count} capabilities
          </Text>
        </TileFooter>
      </Stack>
    </Card>
  );
}

export function ScoreRing({ result }: { result: SearchResult }) {
  return (
    <RingProgress
      size={TILE_RING_SIZE}
      thickness={TILE_RING_THICKNESS}
      roundCaps
      sections={[{ value: result.final * PERCENT, color: LABEL_COLORS[result.label] }]}
      label={
        <Text ta="center" size="xs" fw="bold">
          {pct(result.final)}
        </Text>
      }
      aria-label={`Match score ${pct(result.final)}`}
    />
  );
}

type ResultTileProps = {
  result: SearchResult;
  requirements: ParsedRequirement[];
  best: boolean;
  onOpen: () => void;
};

/** Search result: score ring and one dot per requirement; opens the evidence drawer. */
export function ResultTile({ result, requirements, best, onOpen }: ResultTileProps) {
  const { app } = result;
  const counts = countStatuses(result.evidence);
  return (
    <Card
      component="button"
      type="button"
      onClick={onOpen}
      className="rb-tile"
      radius="lg"
      padding="md"
      data-best={best}
      data-muted={!result.recommended}
      data-testid="result-tile"
      aria-label={`${app.name}, ${LABEL_TEXT[result.label]}, show evidence`}
    >
      <Stack gap="sm" h="100%">
        <TileHeader
          name={app.name}
          subtitle={subtitle(app.domains, app.lifecycle_status)}
          aside={<ScoreRing result={result} />}
        />
        <Text size="sm" c="dimmed" lineClamp={TILE_DESCRIPTION_LINES}>
          {app.short_description}
        </Text>
        <Group gap="xs" wrap="nowrap">
          <RequirementDots result={result} requirements={requirements} />
          {result.flags.length > 0 ? (
            <Text size="xs" c="red">
              {result.flags.map((f) => FLAG_TEXT[f] ?? f).join(", ")}
            </Text>
          ) : (
            <Text size="xs" c="dimmed">
              {counts.covered} of {result.evidence.length} covered
            </Text>
          )}
        </Group>
        <TileFooter>
          <Owner name={app.maintainers[0]} />
          <Badge color={LABEL_COLORS[result.label]} variant="light" style={{ flexShrink: 0 }}>
            {LABEL_TEXT[result.label]}
          </Badge>
        </TileFooter>
      </Stack>
    </Card>
  );
}

/** Requirements no app covers, shown as the last tile of the result grid. */
export function GapTile({ gaps, requirements }: { gaps: number[]; requirements: ParsedRequirement[] }) {
  const byIdx = new Map(requirements.map((r) => [r.idx, r.text]));
  return (
    <Card
      radius="lg"
      padding="md"
      bg="transparent"
      style={{ border: "1px dashed var(--rb-tile-border)" }}
      data-testid="catalog-gaps"
    >
      <Stack gap="xs">
        <Group gap="xs">
          <IconPuzzle size={ICON_SIZE.md} />
          <Text fw={600} size="sm">
            Gap in the catalog
          </Text>
        </Group>
        <Text size="sm" c="dimmed">
          No app covers:
        </Text>
        <List size="sm">
          {gaps.map((i) => (
            <List.Item key={i}>{byIdx.get(i) ?? `Requirement ${i + 1}`}</List.Item>
          ))}
        </List>
      </Stack>
    </Card>
  );
}
