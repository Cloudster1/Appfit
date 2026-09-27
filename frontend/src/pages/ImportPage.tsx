import { Alert, Anchor, Button, Card, Group, Select, Stack, Switch, Text, Title } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconDownload, IconFileUpload, IconUpload, IconX } from "@tabler/icons-react";
import { useState } from "react";

import { rawFetch } from "../api/client";
import { useImport, type ImportReport } from "../api/hooks";
import { notifyError, notifySuccess } from "../components/common/notify";
import { ImportReportView } from "../components/import/ImportReportView";
import { CONTENT_MAX_WIDTH, DROPZONE_MIN_HEIGHT, ICON_SIZE, MAX_UPLOAD_BYTES } from "../config";

const ACCEPT = ["text/csv", "application/json", "text/plain", "application/vnd.ms-excel", ".csv", ".json"];

async function download(url: string, filename: string) {
  try {
    const response = await rawFetch(url);
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (e) {
    notifyError(e, "Download failed");
  }
}

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"upsert" | "create_only">("upsert");
  const [skipInvalid, setSkipInvalid] = useState(false);
  const [report, setReport] = useState<ImportReport | null>(null);
  const importer = useImport();

  const run = async (dryRun: boolean, target: File | null = file) => {
    if (!target) return;
    try {
      const res = await importer.mutateAsync({ file: target, mode, dryRun, skipInvalid });
      setReport(res);
      if (res.committed) notifySuccess(`Imported ${target.name}; new texts are being indexed`);
    } catch (e) {
      setReport(null);
      notifyError(e, "Import failed");
    }
  };

  return (
    <Stack maw={CONTENT_MAX_WIDTH} mx="auto">
      <Stack gap={0}>
        <Title order={2}>Import and export</Title>
        <Text c="dimmed">
          Upload a CSV (comma, semicolon or tab separated; UTF-8 or Windows-1252) or JSON file. Every upload
          first runs as a dry run so you can review the changes before applying them.
        </Text>
      </Stack>

      <Card withBorder>
        <Stack>
          <Dropzone
            onDrop={(files) => {
              const f = files[0] ?? null;
              setFile(f);
              setReport(null);
              void run(true, f);
            }}
            onReject={() =>
              notifyError("Only .csv and .json files up to 10 MB are accepted", "File rejected")
            }
            maxSize={MAX_UPLOAD_BYTES}
            accept={ACCEPT}
            multiple={false}
            loading={importer.isPending}
          >
            <Group justify="center" gap="xl" mih={DROPZONE_MIN_HEIGHT} style={{ pointerEvents: "none" }}>
              <Dropzone.Accept>
                <IconUpload size={ICON_SIZE.xl} />
              </Dropzone.Accept>
              <Dropzone.Reject>
                <IconX size={ICON_SIZE.xl} />
              </Dropzone.Reject>
              <Dropzone.Idle>
                <IconFileUpload size={ICON_SIZE.xl} />
              </Dropzone.Idle>
              <Stack gap={0}>
                <Text size="lg">{file ? file.name : "Drop a CSV or JSON file here, or click to select"}</Text>
                <Text size="sm" c="dimmed">
                  Missing columns keep existing values; empty cells clear them. Apps are matched by slug.
                </Text>
              </Stack>
            </Group>
          </Dropzone>

          <Group align="flex-end">
            <Select
              label="Mode"
              value={mode}
              allowDeselect={false}
              onChange={(v) => setMode((v as "upsert" | "create_only") ?? "upsert")}
              data={[
                { value: "upsert", label: "Create and update" },
                { value: "create_only", label: "Only create new apps" },
              ]}
            />
            <Switch
              label="Skip invalid rows"
              checked={skipInvalid}
              onChange={(e) => setSkipInvalid(e.currentTarget.checked)}
            />
            <Button variant="default" disabled={!file} loading={importer.isPending} onClick={() => run(true)}>
              Dry run again
            </Button>
            <Button
              disabled={!file || !report || (report.errors.length > 0 && !skipInvalid)}
              loading={importer.isPending}
              onClick={() => run(false)}
            >
              Apply import
            </Button>
          </Group>

          {report && (
            <>
              <Alert color={report.committed ? "teal" : "blue"} variant="light">
                {report.committed
                  ? "Import applied."
                  : report.dry_run
                    ? "Dry run: nothing has been written yet. Review the result and click Apply import."
                    : "Nothing was written because of errors."}
              </Alert>
              <ImportReportView report={report} />
            </>
          )}
        </Stack>
      </Card>

      <Card withBorder>
        <Stack gap="xs">
          <Title order={4}>Templates and export</Title>
          <Group gap="xs">
            <Button
              variant="light"
              leftSection={<IconDownload size={ICON_SIZE.sm} />}
              onClick={() => download("/api/import/template.csv", "appfit-template.csv")}
            >
              CSV template
            </Button>
            <Button
              variant="light"
              leftSection={<IconDownload size={ICON_SIZE.sm} />}
              onClick={() =>
                download("/api/import/interfaces-template.csv", "appfit-interfaces-template.csv")
              }
            >
              Interfaces CSV template
            </Button>
            <Button
              variant="light"
              leftSection={<IconDownload size={ICON_SIZE.sm} />}
              onClick={() => download("/api/export?format=json", "appfit-export.json")}
            >
              Export JSON
            </Button>
            <Button
              variant="light"
              leftSection={<IconDownload size={ICON_SIZE.sm} />}
              onClick={() => download("/api/export?format=csv", "appfit-export.csv")}
            >
              Export CSV
            </Button>
            <Button
              variant="light"
              leftSection={<IconDownload size={ICON_SIZE.sm} />}
              onClick={() => download("/api/export?format=csv&kind=interfaces", "appfit-interfaces.csv")}
            >
              Export interfaces CSV
            </Button>
          </Group>
          <Text size="sm" c="dimmed">
            CSV multi-value cells use &quot;|&quot; as separator. Maintainers:{" "}
            <code>owner:Jane Doe &lt;jane@corp.de&gt;</code>. Links: <code>Wiki=https://...</code>. Extra
            attributes: columns named <code>extra.&lt;key&gt;</code>. A CSV with <code>from</code> and{" "}
            <code>to</code> columns is read as interfaces; an endpoint is <code>app:slug</code> or{" "}
            <code>system:Name</code>. JSON files hold apps, external systems and interfaces together, and
            interfaces may refer to apps of the same file. The JSON format is described by the{" "}
            <Anchor href="/api/import/schema.json" target="_blank">
              JSON schema
            </Anchor>
            ; exports can be re-imported unchanged.
          </Text>
        </Stack>
      </Card>
    </Stack>
  );
}
