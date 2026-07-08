import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { VerdictBadge } from "@/components/VerdictBadge";

test("detect verdict shows label + score + confidence and a danger tone", () => {
  render(<VerdictBadge kind="detect" label="MEMORIZED-CODE-LIKELY" score={0.91} confidence={0.8} />);
  const badge = screen.getByTestId("verdict-badge");
  expect(badge).toHaveTextContent("MEMORIZED-CODE-LIKELY");
  expect(badge).toHaveTextContent("91%");
  expect(badge).toHaveTextContent("80%");
  expect(badge.className).toContain("red");
});
