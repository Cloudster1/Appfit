import { PERCENT } from "../../config";

export function pct(value: number): string {
  return `${Math.round(value * PERCENT)}%`;
}

export type ReqStatus = "covered" | "partial" | "gap";

export function countStatuses(evidence: { status: ReqStatus }[]): Record<ReqStatus, number> {
  const counts: Record<ReqStatus, number> = { covered: 0, partial: 0, gap: 0 };
  for (const e of evidence) counts[e.status] += 1;
  return counts;
}

export const LABEL_TEXT: Record<string, string> = {
  strong: "Strong match",
  partial: "Partial match",
  weak: "Weak match",
};

export const FLAG_TEXT: Record<string, string> = {
  missing_must_have: "Misses a must-have",
  not_indexed: "Not indexed yet",
};

/** Merge tag lists without duplicates; a name can exist in several tag categories. */
export function uniqueTags(...lists: string[][]): string[] {
  return [...new Set(lists.flat())];
}

export const STATUS_TEXT: Record<ReqStatus, string> = {
  covered: "Covered",
  partial: "Partially covered",
  gap: "Not covered",
};

type Requirement = { idx: number; text: string; priority?: string | null };
type Scored = {
  app: { name: string };
  final: number;
  evidence: {
    req_idx: number;
    status: ReqStatus;
    similarity: number;
    via: string;
    capability?: { text: string } | null;
    interface?: EvidenceInterface | null;
  }[];
};

type EvidenceInterface = { name: string; direction: string; counterpart: { name: string } };

const DIRECTION_WORDS: Record<string, string> = { outgoing: "to", incoming: "from", both: "with" };

/** "Interface to SAP S/4HANA: Invoice posting" from the matched app's point of view. */
export function interfaceText(i: EvidenceInterface): string {
  return `Interface ${DIRECTION_WORDS[i.direction] ?? "with"} ${i.counterpart.name}: ${i.name}`;
}

/** Must-have requirements the app covers; total is 0 when no requirement is marked must. */
export function mustHaves(result: Scored, requirements: Requirement[]): { covered: number; total: number } {
  const must = new Set(requirements.filter((r) => r.priority === "must").map((r) => r.idx));
  const covered = result.evidence.filter((e) => must.has(e.req_idx) && e.status === "covered").length;
  return { covered, total: must.size };
}

/** Single-line input doubles as a catalog keyword; several lines are a requirement list. */
export function keywordFromText(text: string): string {
  const trimmed = text.trim();
  return trimmed && !trimmed.includes("\n") ? trimmed : "";
}

export function evidenceText(ev: Scored["evidence"][number]): string {
  if (ev.via === "interface" && ev.interface) return interfaceText(ev.interface);
  if (ev.via === "capability" && ev.capability) return ev.capability.text;
  if (ev.via === "summary") return "Related to the app description";
  return "";
}

// Spreadsheets run cells that start with these characters as formulas.
const FORMULA_START = /^[=+\-@\t\r]/;

function csvCell(value: string, delimiter: string): string {
  const safe = FORMULA_START.test(value) ? `'${value}` : value;
  const needsQuotes = safe.includes(delimiter) || /["\r\n]/.test(safe);
  return needsQuotes ? `"${safe.replaceAll('"', '""')}"` : safe;
}

/** Requirement x app matrix as CSV: a score row, then one row per requirement. */
export function matrixCsv(results: Scored[], requirements: Requirement[], delimiter: string): string {
  const header = ["Priority", "Requirement", ...results.map((r) => r.app.name)];
  const scores = ["", "Score", ...results.map((r) => pct(r.final))];
  const rows = requirements.map((req) => [
    req.priority ?? "",
    req.text,
    ...results.map((r) => {
      const ev = r.evidence.find((e) => e.req_idx === req.idx);
      if (!ev) return "";
      const detail = evidenceText(ev);
      return `${ev.status} ${pct(ev.similarity)}${detail ? `: ${detail}` : ""}`;
    }),
  ]);
  return [header, scores, ...rows]
    .map((row) => row.map((c) => csvCell(c, delimiter)).join(delimiter))
    .join("\r\n");
}

/** Two-letter monogram from the first two words, ignoring punctuation such as "(Alt)". */
export function initials(name: string): string {
  const words = name
    .split(/\s+/)
    .map((w) => w.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0]!.slice(0, 2);
  return (words[0]![0]! + words[1]![0]!).toUpperCase();
}
