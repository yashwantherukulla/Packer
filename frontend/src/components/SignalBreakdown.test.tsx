import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { SignalBreakdown } from "@/components/SignalBreakdown";

test("renders one card per signal with evidence", () => {
  render(
    <SignalBreakdown
      signals={[
        { name: "spectral", score: 0.9, confidence: 0.7, evidence: { alpha: 2.1, outliers: 5 } },
        { name: "weight_norm", score: 0.4, confidence: 0.5, evidence: {} },
      ]}
    />,
  );
  expect(screen.getByText("spectral")).toBeInTheDocument();
  expect(screen.getByText("weight_norm")).toBeInTheDocument();
  expect(screen.getByText("alpha")).toBeInTheDocument();
  expect(screen.getByText("2.1")).toBeInTheDocument();
});
