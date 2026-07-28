import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { JobFailureCard } from "@/components/JobFailureCard";

test("renders the error message and code", () => {
  render(
    <JobFailureCard
      error="corpus token length 21800 exceeds context_len 1024"
      errorCode="pack_error"
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent(/job failed/i);
  expect(screen.getByRole("alert")).toHaveTextContent(/context_len 1024/i);
  expect(screen.getByTestId("job-error-code")).toHaveTextContent("pack_error");
});
