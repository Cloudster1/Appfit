import { ActionIcon, Button, Group, Select, Stack, Text, Textarea, Tooltip } from "@mantine/core";
import { IconThumbDown, IconThumbUp } from "@tabler/icons-react";
import { useState } from "react";

import { useApps, useSearchFeedback } from "../../api/hooks";
import { ALL_APPS_PAGE_SIZE, ICON_SIZE, NARROW_FORM_WIDTH } from "../../config";
import { notifyError, notifySuccess } from "../common/notify";

export function FeedbackButtons({ logId }: { logId: string }) {
  const feedback = useSearchFeedback();
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [expected, setExpected] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);
  const apps = useApps({ sort: "name", size: ALL_APPS_PAGE_SIZE });

  const send = async (r: "up" | "down") => {
    try {
      await feedback.mutateAsync({
        logId,
        body: { rating: r, expected_app_slug: expected, comment: comment.trim() || null },
      });
      setSent(true);
      notifySuccess("Thanks, your feedback helps to tune the matching.");
    } catch (e) {
      notifyError(e, "Feedback could not be saved");
    }
  };

  if (sent) {
    return (
      <Text size="sm" c="dimmed">
        Thanks for your feedback.
      </Text>
    );
  }

  return (
    <Stack gap="xs">
      <Group gap="xs">
        <Text size="sm">Were these results helpful?</Text>
        <Tooltip label="Yes">
          <ActionIcon variant="light" color="teal" aria-label="Helpful" onClick={() => send("up")}>
            <IconThumbUp size={ICON_SIZE.sm} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label="No">
          <ActionIcon
            variant={rating === "down" ? "filled" : "light"}
            color="red"
            aria-label="Not helpful"
            onClick={() => setRating("down")}
          >
            <IconThumbDown size={ICON_SIZE.sm} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {rating === "down" && (
        <Stack gap="xs" maw={NARROW_FORM_WIDTH}>
          <Select
            label="Which app did you expect? (optional)"
            searchable
            clearable
            data={(apps.data?.items ?? []).map((a) => ({ value: a.slug, label: a.name }))}
            value={expected}
            onChange={setExpected}
          />
          <Textarea
            label="Comment (optional)"
            autosize
            minRows={2}
            value={comment}
            onChange={(e) => setComment(e.currentTarget.value)}
          />
          <Group>
            <Button size="xs" loading={feedback.isPending} onClick={() => send("down")}>
              Send feedback
            </Button>
          </Group>
        </Stack>
      )}
    </Stack>
  );
}
