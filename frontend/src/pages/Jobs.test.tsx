import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { Jobs } from "@/pages/Jobs";

vi.mock("@/hooks/useJob", () => ({
  useJobs: () => ({ data: [{ id: "abcdef12", type: "detect", status: "succeeded" }] }),
}));

test("lists jobs with links to detail", () => {
  render(
    <MemoryRouter>
      <Jobs />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("detect");
  expect(screen.getByRole("link", { name: /abcdef12/i })).toHaveAttribute("href", "/jobs/abcdef12");
});
