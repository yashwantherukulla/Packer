import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { Detect } from "@/pages/Detect";
import type { Report } from "@/api/types";

const mutate = vi.fn();
vi.mock("@/hooks/useSubmit", () => ({
  useSubmitDetect: () => ({ mutate, data: { id: "j1", result_ref: "r1" } }),
}));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => ({ event: null, connected: true, status: "succeeded" }),
}));
vi.mock("@/hooks/useJob", () => ({
  useReport: () => ({
    data: {
      kind: "detect",
      schema_version: "1.0",
      verdict: { label: "UNLIKELY", score: 0.1, confidence: 0.6 },
      sections: [],
      evidence: {},
      limitations: ["Signature, not proof."],
    } as unknown as Report,
  }),
}));

afterEach(() => vi.clearAllMocks());

test("submits a model_ref and renders the detect report", async () => {
  render(<Detect />);
  await userEvent.type(screen.getByTestId("model-ref"), "Qwen/Qwen2.5-0.5B");
  await userEvent.click(screen.getByTestId("submit"));
  expect(mutate).toHaveBeenCalledWith({ model_ref: "Qwen/Qwen2.5-0.5B" });
  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
});
