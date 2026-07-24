import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { Jobs } from "@/pages/Jobs";

vi.mock("@/hooks/useJob", () => ({
  useJobs: () => ({
    data: [
      {
        id: "abcdef12",
        type: "detect",
        status: "succeeded",
        created_at: "2026-07-23T10:00:00Z",
        finished_at: "2026-07-23T10:01:30Z",
        result_ref: "report:r1",
      },
    ],
  }),
}));

test("lists jobs with links to detail", () => {
  render(
    <MemoryRouter>
      <Jobs />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("detect");
  expect(screen.getByRole("link", { name: /abcdef12/i })).toHaveAttribute("href", "/jobs/abcdef12");
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("2026-07-23 10:00:00 UTC");
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("2026-07-23 10:01:30 UTC");
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("report:r1");
});
