import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { Pack } from "@/pages/Pack";
import type { ProgressView } from "@/hooks/useJobProgress";

const mutate = vi.fn();
const submitMock: { data: { id: string } | undefined; isError: boolean; error: Error | null } = {
  data: { id: "job-1" },
  isError: false,
  error: null,
};
const progressMock: {
  event: ProgressView | null;
  connected: boolean;
  status: string;
} = {
  event: { step: "train", pct: 0.5, detail: "epoch 100" },
  connected: true,
  status: "running",
};
const jobMock: {
  data: { status: string; error: string | null; error_code: string | null; result_ref: string | null };
} = {
  data: { status: "running", error: null, error_code: null, result_ref: null },
};
const artifactMock: { data: unknown } = { data: undefined };

vi.mock("@/hooks/useSubmit", () => ({
  useSubmitPack: () => ({ mutate, ...submitMock }),
}));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => progressMock,
}));
vi.mock("@/hooks/useJob", () => ({
  useJob: () => jobMock,
  useArtifact: () => artifactMock,
}));

afterEach(() => {
  vi.clearAllMocks();
  progressMock.event = { step: "train", pct: 0.5, detail: "epoch 100" };
  progressMock.connected = true;
  progressMock.status = "running";
  jobMock.data = { status: "running", error: null, error_code: null, result_ref: null };
  artifactMock.data = undefined;
  submitMock.data = { id: "job-1" };
  submitMock.isError = false;
  submitMock.error = null;
  window.sessionStorage.clear();
});

test("uploading a zip submits a pack job and streams progress", async () => {
  render(<Pack />);
  await userEvent.upload(
    screen.getByLabelText(/repository/i),
    new File(["x"], "toy.zip", { type: "application/zip" }),
  );
  expect(mutate).toHaveBeenCalledOnce();
  expect(screen.getByTestId("job-progress")).toHaveTextContent("train");
});

test("renders the pack error instead of hanging on progress after failure", () => {
  progressMock.event = null;
  progressMock.connected = false;
  progressMock.status = "failed";
  jobMock.data = {
    status: "failed",
    error: "corpus token length 21800 exceeds context_len 1024",
    error_code: "pack_error",
    result_ref: null,
  };

  render(<Pack />);
  expect(screen.getByRole("alert")).toHaveTextContent(/job failed/i);
  expect(screen.getByRole("alert")).toHaveTextContent(/context_len 1024/i);
  expect(screen.queryByTestId("job-progress")).not.toBeInTheDocument();
});

test("renders the submission error message when upload fails before queueing", () => {
  submitMock.isError = true;
  submitMock.error = new Error("multipart upload rejected");

  render(<Pack />);
  expect(screen.getByRole("alert")).toHaveTextContent(/submission failed/i);
  expect(screen.getByRole("alert")).toHaveTextContent(/multipart upload rejected/i);
});

test("restores the last pack job so the artifact id stays available", () => {
  submitMock.data = undefined;
  progressMock.event = null;
  progressMock.connected = false;
  progressMock.status = "succeeded";
  jobMock.data = {
    status: "succeeded",
    error: null,
    error_code: null,
    result_ref: "artifact:a1",
  };
  artifactMock.data = {
    id: "a1",
    metrics_json: {
      original_bytes: 180_000,
      gzip_bytes: 48_000,
      artifact_bytes: 7_050_000,
      compression_ratio_vs_original: 39.2,
    },
  };
  window.sessionStorage.setItem("pack:last-job-id", "job-restored");

  render(
    <MemoryRouter>
      <Pack />
    </MemoryRouter>,
  );
  expect(screen.getByTestId("artifact-id")).toHaveValue("a1");
});
