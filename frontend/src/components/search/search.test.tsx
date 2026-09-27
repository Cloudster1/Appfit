import { fireEvent, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders, sampleResponse } from "../../test/utils";
import { ComplianceMatrix } from "./ComplianceMatrix";
import { EvidenceList } from "./EvidenceList";
import { initials, keywordFromText, matrixCsv, mustHaves } from "./format";
import { CatalogGapsAlert, NoMatchBanner } from "./NoMatchBanner";
import { RequirementEditor, type EditableRequirement } from "./RequirementEditor";

const [firstResult] = sampleResponse.results;

describe("EvidenceList", () => {
  it("shows matched capability, description fallback and gaps", () => {
    renderWithProviders(<EvidenceList result={firstResult!} requirements={sampleResponse.requirements} />);
    const rows = screen.getAllByTestId("evidence-row");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).getByText("OCR extraction of invoice data")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("Must")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("ocr")).toBeInTheDocument();
    expect(within(rows[1]!).getByText(/Related to the app description/)).toBeInTheDocument();
    expect(within(rows[0]!).getByText("81%")).toBeInTheDocument();
  });
});

describe("ComplianceMatrix", () => {
  const renderMatrix = () =>
    renderWithProviders(
      <ComplianceMatrix
        results={sampleResponse.results}
        requirements={sampleResponse.requirements}
        gaps={sampleResponse.catalog_gaps}
      />,
    );

  it("renders one row per requirement and a status cell per app", () => {
    renderMatrix();
    expect(screen.getByRole("link", { name: "Invoice Hub" })).toHaveAttribute("href", "/apps/invoice-hub");
    const covered = screen.getByTestId("cell-0-invoice-hub");
    expect(within(covered).getByLabelText("Covered")).toBeInTheDocument();
    expect(covered).toHaveTextContent("OCR extraction of invoice data");
    expect(covered).toHaveTextContent("81%");
    expect(screen.getByTestId("cell-1-invoice-hub")).toHaveTextContent("Related to the app description");
    expect(
      within(screen.getByTestId("cell-2-invoice-hub")).getByLabelText("Not covered"),
    ).toBeInTheDocument();
  });

  it("marks catalog gaps and totals the must-haves per app", () => {
    renderMatrix();
    expect(screen.getByTestId("matrix-gap-2")).toHaveTextContent("Catalog gap");
    expect(screen.queryByTestId("matrix-gap-0")).not.toBeInTheDocument();
    expect(screen.getByText("Must-haves covered")).toBeInTheDocument();
    expect(screen.getByTestId("matrix-total-invoice-hub")).toHaveTextContent("1 of 1");
  });

  it("exports the matrix as CSV", async () => {
    // jsdom has no object URLs; capture the blob instead.
    let exported: Blob | undefined;
    URL.createObjectURL = vi.fn((blob: Blob) => {
      exported = blob;
      return "blob:matrix";
    });
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderMatrix();
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    expect(click).toHaveBeenCalledTimes(1);
    const text = await exported!.text();
    expect(text).toContain("Priority;Requirement;Invoice Hub");
    click.mockRestore();
  });
});

describe("matrix helpers", () => {
  const [result] = sampleResponse.results;

  it("writes a score row and one row per requirement", () => {
    const csv = matrixCsv(sampleResponse.results, sampleResponse.requirements, ";").split("\r\n");
    expect(csv[0]).toBe("Priority;Requirement;Invoice Hub");
    expect(csv[1]).toBe(";Score;82%");
    expect(csv[2]).toBe("must;OCR for invoices;covered 81%: OCR extraction of invoice data");
    expect(csv).toHaveLength(2 + sampleResponse.requirements.length);
  });

  it("quotes delimiters and neutralizes spreadsheet formulas", () => {
    const requirements = [
      { idx: 0, text: "Export; import", priority: null, weight: 1 },
      { idx: 1, text: "=HYPERLINK(1)", priority: null, weight: 1 },
    ];
    const lines = matrixCsv([], requirements, ";").split("\r\n");
    expect(lines[2]).toBe(';"Export; import"');
    expect(lines[3]).toBe(";'=HYPERLINK(1)");
  });

  it("counts covered must-haves", () => {
    expect(mustHaves(result!, sampleResponse.requirements)).toEqual({ covered: 1, total: 1 });
    const none = sampleResponse.requirements.map((r) => ({ ...r, priority: null }));
    expect(mustHaves(result!, none)).toEqual({ covered: 0, total: 0 });
  });

  it("builds monograms without punctuation", () => {
    expect(initials("Rechnungsportal (Alt)")).toBe("RA");
    expect(initials("InvoiceFlow AP")).toBe("IA");
    expect(initials("Belegfix")).toBe("Be");
    expect(initials("  ")).toBe("?");
  });

  it("treats only a single line as catalog keyword", () => {
    expect(keywordFromText("  invoice  ")).toBe("invoice");
    expect(keywordFromText("OCR\nSAP")).toBe("");
    expect(keywordFromText("   ")).toBe("");
  });
});

describe("NoMatchBanner", () => {
  it("lists requirements that no app covers", () => {
    renderWithProviders(<NoMatchBanner gaps={[2]} requirements={sampleResponse.requirements} />);
    expect(screen.getByText("No good match in the catalog")).toBeInTheDocument();
    expect(screen.getByText("Canteen menu")).toBeInTheDocument();
  });

  it("renders nothing for an empty gap list", () => {
    renderWithProviders(<CatalogGapsAlert gaps={[]} requirements={sampleResponse.requirements} />);
    expect(screen.queryByTestId("catalog-gaps")).not.toBeInTheDocument();
  });
});

function EditorHarness({ initial }: { initial: EditableRequirement[] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <RequirementEditor value={value} onChange={setValue} maxItems={3} />
      <pre data-testid="state">{JSON.stringify(value)}</pre>
    </>
  );
}

describe("RequirementEditor", () => {
  it("edits, adds and removes requirements and respects the maximum", () => {
    renderWithProviders(<EditorHarness initial={[{ text: "SSO", priority: null }]} />);
    const state = () => JSON.parse(screen.getByTestId("state").textContent ?? "[]") as EditableRequirement[];

    fireEvent.change(screen.getByLabelText("Requirement 1"), { target: { value: "SSO via Entra ID" } });
    fireEvent.click(screen.getByRole("button", { name: "Add requirement" }));
    fireEvent.click(screen.getByRole("button", { name: "Add requirement" }));
    expect(state().map((r) => r.text)).toEqual(["SSO via Entra ID", "", ""]);
    expect(screen.getByRole("button", { name: "Add requirement" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Remove requirement 2" }));
    expect(state()).toHaveLength(2);
  });
});
