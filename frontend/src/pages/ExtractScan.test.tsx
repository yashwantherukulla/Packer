import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ExtractScan } from "@/pages/ExtractScan";
import type { Report } from "@/api/types";

const progressMock = { event: null, connected: true, status: "succeeded" };
const jobMock = { data: { status: "succeeded", result_ref: "report:r2", error: null, error_code: null } };

vi.mock("@/hooks/useSubmit", () => ({
  useSubmitScan: () => ({ mutate: vi.fn(), data: { id: "j2" } }),
}));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => progressMock,
}));
vi.mock("@/hooks/useJob", () => ({
  useJob: () => jobMock,
  useReport: () => ({
    data: {
      kind: "scan",
      schema_version: "1.0",
      verdict: { label: "benign", score: 0.1, confidence: 0.7 },
      sections: [{ type: "findings", title: "Static", data: { findings: [] } }],
      evidence: { extraction: { mode: "exact" } },
      limitations: [],
    } as unknown as Report,
  }),
}));

afterEach(() => vi.clearAllMocks());

test("renders the byte-exact banner and the scan report", () => {
  render(<ExtractScan />);
  expect(screen.getByTestId("reconstruction")).toHaveTextContent(/byte-exact/i);
  expect(screen.getByTestId("report-scan")).toBeInTheDocument();
});
