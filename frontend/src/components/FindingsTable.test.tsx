import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { FindingsTable } from "@/components/FindingsTable";

const FINDINGS = [
  { severity: "low", rule: "B101", file: "a.py", line: 3, note: "assert" },
  { severity: "high", rule: "B602", file: "b.py", line: 9, note: "shell=True" },
];

test("defaults to severity-descending, toggles on header click", async () => {
  render(<FindingsTable findings={FINDINGS} />);
  const firstRow = () => within(screen.getByTestId("findings-table")).getAllByRole("row")[1];
  expect(firstRow()).toHaveTextContent("high");
  await userEvent.click(screen.getByTestId("sort-severity"));
  expect(firstRow()).toHaveTextContent("low");
});
