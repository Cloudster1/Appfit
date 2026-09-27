import {
  Alert,
  Button,
  Card,
  Group,
  Select,
  SimpleGrid,
  Stack,
  TagsInput,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertTriangle, IconDeviceFloppy } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useApp, useEnums, useSaveApp, useSearchConfig, useTags } from "../api/hooks";
import { CapabilityListEditor } from "../components/apps/CapabilityListEditor";
import {
  EMPTY_APP,
  toFormValues,
  toPayload,
  urlError,
  type AppFormValues,
} from "../components/apps/formModel";
import { LinksEditor, MaintainersEditor } from "../components/apps/RowEditors";
import { notifySuccess } from "../components/common/notify";
import { QueryState } from "../components/common/QueryState";
import { CONTENT_MAX_WIDTH, ICON_SIZE, SHORT_DESCRIPTION_MAX_LEN, SLUG_PATTERN } from "../config";

const DESCRIPTION_MIN_ROWS = 4;

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card withBorder>
      <Stack gap="sm">
        <Stack gap={0}>
          <Title order={4}>{title}</Title>
          {description && (
            <Text size="sm" c="dimmed">
              {description}
            </Text>
          )}
        </Stack>
        {children}
      </Stack>
    </Card>
  );
}

export function AppEditPage() {
  const { slug } = useParams();
  const isNew = !slug;
  const existing = useApp(slug);
  const enums = useEnums();
  const tags = useTags();
  const config = useSearchConfig();
  const save = useSaveApp(slug);
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<AppFormValues>({
    initialValues: EMPTY_APP,
    validate: {
      name: (v) => (v.trim() ? null : "Name is required"),
      slug: (v) => (v.trim() && !SLUG_PATTERN.test(v.trim()) ? "Lowercase letters, digits and -" : null),
      short_description: (v) =>
        v.length > SHORT_DESCRIPTION_MAX_LEN ? `At most ${SHORT_DESCRIPTION_MAX_LEN} characters` : null,
      homepage_url: urlError,
      repo_url: urlError,
      docs_url: urlError,
      links: { url: urlError },
      maintainers: {
        name: (v, values, path) => {
          const idx = Number(path.split(".")[1]);
          return v.trim() || values.maintainers[idx]?.email.trim() ? null : "Name or email required";
        },
      },
    },
  });

  const { setValues, resetDirty } = form;
  useEffect(() => {
    if (existing.data) {
      setValues(toFormValues(existing.data));
      resetDirty(toFormValues(existing.data));
    }
    // Only re-initialize when another app is loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing.data?.id]);

  const suggestions = (category: string) =>
    (tags.data ?? []).filter((t) => t.category === category).map((t) => t.name);

  const submit = form.onSubmit(async (values) => {
    setServerError(null);
    try {
      const app = await save.mutateAsync(toPayload(values));
      notifySuccess(isNew ? "App created; it will be searchable in a few seconds" : "Changes saved");
      navigate(`/apps/${app.slug}`);
    } catch (e) {
      setServerError(e instanceof Error ? e.message : String(e));
    }
  });

  const body = (
    <form onSubmit={submit}>
      <Stack maw={CONTENT_MAX_WIDTH} mx="auto">
        <Group justify="space-between">
          <Title order={2}>{isNew ? "New application" : `Edit ${existing.data?.name ?? ""}`}</Title>
          <Group gap="xs">
            <Button variant="default" component={Link} to={isNew ? "/" : `/apps/${slug}`}>
              Cancel
            </Button>
            <Button
              type="submit"
              loading={save.isPending}
              leftSection={<IconDeviceFloppy size={ICON_SIZE.sm} />}
            >
              Save
            </Button>
          </Group>
        </Group>

        {serverError && (
          <Alert color="red" icon={<IconAlertTriangle />} title="Could not save">
            {serverError}
          </Alert>
        )}

        <Section title="Basics">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput label="Name" withAsterisk {...form.getInputProps("name")} />
            <TextInput
              label="Slug"
              description="URL identifier; derived from the name when empty"
              {...form.getInputProps("slug")}
            />
          </SimpleGrid>
          <TextInput
            label="Short description"
            description="One sentence shown in lists and search results"
            maxLength={SHORT_DESCRIPTION_MAX_LEN}
            {...form.getInputProps("short_description")}
          />
          <Textarea
            label="Description"
            autosize
            minRows={DESCRIPTION_MIN_ROWS}
            {...form.getInputProps("description")}
          />
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <Select
              label="Lifecycle"
              data={enums.data?.lifecycle_status ?? []}
              allowDeselect={false}
              {...form.getInputProps("lifecycle_status")}
            />
            <TextInput label="Vendor" {...form.getInputProps("vendor")} />
            <TextInput label="Version" {...form.getInputProps("version")} />
            <TextInput
              label="License"
              placeholder="e.g. Apache-2.0, Proprietary"
              {...form.getInputProps("license")}
            />
            <Select
              label="License type"
              clearable
              data={enums.data?.license_type ?? []}
              {...form.getInputProps("license_type")}
            />
          </SimpleGrid>
        </Section>

        <Section
          title="Capabilities"
          description="What the app does or guarantees. Matching compares every user requirement with each of these statements."
        >
          <CapabilityListEditor form={form} warnLen={config.data?.capability_atomic_warn_len} />
        </Section>

        <Section title="Classification">
          <TagsInput label="Tags" data={suggestions("general")} clearable {...form.getInputProps("tags")} />
          <TagsInput
            label="Business domains"
            data={suggestions("domain")}
            clearable
            {...form.getInputProps("domains")}
          />
          <TagsInput
            label="Tech stack"
            data={suggestions("tech")}
            clearable
            {...form.getInputProps("tech_stack")}
          />
        </Section>

        <Section title="Maintainers">
          <MaintainersEditor form={form} />
        </Section>

        <Section title="Links">
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <TextInput label="Homepage" {...form.getInputProps("homepage_url")} />
            <TextInput label="Documentation" {...form.getInputProps("docs_url")} />
            <TextInput label="Repository" {...form.getInputProps("repo_url")} />
          </SimpleGrid>
          <LinksEditor form={form} />
        </Section>
      </Stack>
    </form>
  );

  if (isNew) return body;
  return (
    <QueryState isPending={existing.isPending} error={existing.error}>
      {body}
    </QueryState>
  );
}
