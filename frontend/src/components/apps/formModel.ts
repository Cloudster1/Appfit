import type { AppIn, AppOut } from "../../api/hooks";

export type CapabilityRow = {
  id: string | null;
  kind: "capability" | "requirement" | "feature";
  text: string;
  details: string;
};

export type MaintainerRow = {
  name: string;
  email: string;
  role: "owner" | "maintainer" | "contact";
  kind: "person" | "team";
  org_unit: string;
};

export type LinkRow = { label: string; url: string };

export type AppFormValues = {
  name: string;
  slug: string;
  short_description: string;
  description: string;
  lifecycle_status: AppIn["lifecycle_status"] & string;
  license: string;
  license_type: string | null;
  vendor: string;
  version: string;
  homepage_url: string;
  repo_url: string;
  docs_url: string;
  tags: string[];
  tech_stack: string[];
  domains: string[];
  maintainers: MaintainerRow[];
  links: LinkRow[];
  capabilities: CapabilityRow[];
  extra: Record<string, unknown>;
};

export const EMPTY_APP: AppFormValues = {
  name: "",
  slug: "",
  short_description: "",
  description: "",
  lifecycle_status: "active",
  license: "",
  license_type: null,
  vendor: "",
  version: "",
  homepage_url: "",
  repo_url: "",
  docs_url: "",
  tags: [],
  tech_stack: [],
  domains: [],
  maintainers: [],
  links: [],
  capabilities: [],
  extra: {},
};

export function toFormValues(app: AppOut): AppFormValues {
  return {
    name: app.name,
    slug: app.slug,
    short_description: app.short_description,
    description: app.description,
    lifecycle_status: app.lifecycle_status,
    license: app.license ?? "",
    license_type: app.license_type ?? null,
    vendor: app.vendor ?? "",
    version: app.version ?? "",
    homepage_url: app.homepage_url ?? "",
    repo_url: app.repo_url ?? "",
    docs_url: app.docs_url ?? "",
    tags: app.tags,
    tech_stack: app.tech_stack,
    domains: app.domains,
    maintainers: app.maintainers.map((m) => ({
      name: m.name,
      email: m.email ?? "",
      role: m.role,
      kind: m.kind,
      org_unit: m.org_unit ?? "",
    })),
    links: app.links.map((l) => ({ label: l.label, url: l.url })),
    capabilities: app.capabilities.map((c) => ({
      id: c.id,
      kind: c.kind,
      text: c.text,
      details: c.details ?? "",
    })),
    extra: app.extra,
  };
}

const orNull = (v: string) => (v.trim() ? v.trim() : null);

export function toPayload(v: AppFormValues): AppIn {
  return {
    name: v.name.trim(),
    slug: orNull(v.slug),
    short_description: v.short_description.trim(),
    description: v.description.trim(),
    lifecycle_status: v.lifecycle_status,
    license: orNull(v.license),
    license_type: (v.license_type || null) as AppIn["license_type"],
    vendor: orNull(v.vendor),
    version: orNull(v.version),
    homepage_url: orNull(v.homepage_url),
    repo_url: orNull(v.repo_url),
    docs_url: orNull(v.docs_url),
    tags: v.tags,
    tech_stack: v.tech_stack,
    domains: v.domains,
    maintainers: v.maintainers
      .filter((m) => m.name.trim() || m.email.trim())
      .map((m) => ({
        name: orNull(m.name),
        email: orNull(m.email),
        role: m.role,
        kind: m.kind,
        org_unit: orNull(m.org_unit),
      })),
    links: v.links
      .filter((l) => l.url.trim())
      .map((l) => ({ label: l.label.trim() || l.url.trim(), url: l.url.trim() })),
    capabilities: v.capabilities
      .filter((c) => c.text.trim())
      .map((c) => ({ id: c.id, kind: c.kind, text: c.text.trim(), details: orNull(c.details) })),
    extra: v.extra,
  };
}

const URL_RE = /^https?:\/\/\S+$/i;
const SENTENCE_BREAK_RE = /[.!?;]\s+\S/;

export function urlError(value: string): string | null {
  return value.trim() && !URL_RE.test(value.trim()) ? "Must start with http:// or https://" : null;
}

export function atomicWarning(text: string, maxLen: number): string | null {
  if (text.length > maxLen)
    return "Long statement: split it into several atomic capabilities for better matching";
  if (SENTENCE_BREAK_RE.test(text.trim()))
    return "Several sentences: one capability per statement matches best";
  return null;
}
