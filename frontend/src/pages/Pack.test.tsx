import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { Pack } from "@/pages/Pack";

const mutate = vi.fn();
vi.mock("@/hooks/useSubmit", () => ({
  useSubmitPack: () => ({ mutate, data: { id: "job-1" }, isError: false }),
}));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => ({
    event: { step: "train", pct: 0.5, detail: "epoch 100" },
    connected: true,
    status: "running",
  }),
}));
vi.mock("@/hooks/useJob", () => ({ useArtifact: () => ({ data: undefined }) }));

afterEach(() => vi.clearAllMocks());

test("uploading a zip submits a pack job and streams progress", async () => {
  render(<Pack />);
  await userEvent.upload(
    screen.getByLabelText(/repository/i),
    new File(["x"], "toy.zip", { type: "application/zip" }),
  );
  expect(mutate).toHaveBeenCalledOnce();
  expect(screen.getByTestId("job-progress")).toHaveTextContent("train");
});
