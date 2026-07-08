import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ReportView } from "@/components/ReportView";
import type { ReportBody } from "@/lib/report-view";

const detect = {
  kind: "detect",
  schema_version: "1.0",
  verdict: { label: "MEMORIZED-CODE-LIKELY", score: 0.9, confidence: 0.8 },
  sections: [
    {
      type: "signals",
      title: "Signals",
      data: { signals: [{ name: "spectral", score: 0.9, confidence: 0.7, evidence: {} }] },
    },
  ],
  evidence: {},
  limitations: ["Signature, not proof: cannot recover code from weights alone."],
} as unknown as ReportBody;

const scan = {
  kind: "scan",
  schema_version: "1.0",
  verdict: { label: "malicious", score: 0.8, confidence: 0.75 },
  sections: [
    {
      type: "findings",
      title: "Static",
      data: { findings: [{ severity: "high", rule: "B602", file: "b.py", line: 9, note: "shell=True" }] },
    },
    {
      type: "behavior",
      title: "Dynamic",
      data: { syscalls: ["execve"], fs_writes: [], blocked_net: ["1.2.3.4:443"], disagreement: null },
    },
  ],
  evidence: {},
  limitations: [],
} as unknown as ReportBody;

test("detect report renders signals + verdict + the 'signature not proof' limitation", () => {
  render(<ReportView report={detect} />);
  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
  expect(screen.getByTestId("signal-breakdown")).toBeInTheDocument();
  expect(screen.getByTestId("limitations")).toHaveTextContent(/signature, not proof/i);
  expect(screen.queryByTestId("findings-table")).not.toBeInTheDocument();
});

test("scan report renders findings + behavior, not signals", () => {
  render(<ReportView report={scan} />);
  expect(screen.getByTestId("report-scan")).toBeInTheDocument();
  expect(screen.getByTestId("findings-table")).toBeInTheDocument();
  expect(screen.getByTestId("behavior-panel")).toBeInTheDocument();
  expect(screen.queryByTestId("signal-breakdown")).not.toBeInTheDocument();
});
