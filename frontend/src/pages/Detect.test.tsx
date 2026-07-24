import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { Detect } from "@/pages/Detect";
import type { Report } from "@/api/types";

const mutate = vi.fn();
const submitMock: { data?: { id: string } } = { data: { id: "j1" } };
const progressMock = { event: null, connected: true, status: "succeeded" };
const jobMock = { data: { status: "succeeded", result_ref: "report:r1", error: null, error_code: null } };

vi.mock("@/hooks/useSubmit", () => ({
  useSubmitDetect: () => ({ mutate, ...submitMock }),
}));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => progressMock,
}));
vi.mock("@/hooks/useJob", () => ({
  useJob: () => jobMock,
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

afterEach(() => {
  vi.clearAllMocks();
  submitMock.data = { id: "j1" };
  window.sessionStorage.clear();
});

test("submits a model_ref and renders the detect report", async () => {
  render(
    <MemoryRouter initialEntries={["/detect"]}>
      <Detect />
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByTestId("model-ref"), "Qwen/Qwen2.5-0.5B");
  await userEvent.click(screen.getByTestId("submit"));
  expect(mutate).toHaveBeenCalledWith({ model_ref: "Qwen/Qwen2.5-0.5B" });
  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
});

test("prefills the model_ref from the detect link query", () => {
  render(
    <MemoryRouter initialEntries={["/detect?model_ref=artifact%3Aa1"]}>
      <Detect />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("model-ref")).toHaveValue("artifact:a1");
});

test("restores the last detect job for the current browser session", () => {
  submitMock.data = undefined;
  window.sessionStorage.setItem("detect:last-job-id", "j-restored");

  render(
    <MemoryRouter initialEntries={["/detect"]}>
      <Detect />
    </MemoryRouter>,
  );

  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
});
