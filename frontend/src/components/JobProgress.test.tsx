import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { JobProgress } from "@/components/JobProgress";

test("renders clamped percent, detail, and connected state", () => {
  render(<JobProgress step="train" pct={0.4} detail="epoch 80/200" status="running" connected />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  expect(screen.getByText("epoch 80/200")).toBeInTheDocument();
  expect(screen.queryByTestId("fallback-indicator")).not.toBeInTheDocument();
});

test("shows the polling fallback indicator when disconnected", () => {
  render(<JobProgress step="train" pct={0.4} status="running" connected={false} />);
  expect(screen.getByTestId("fallback-indicator")).toBeInTheDocument();
});
