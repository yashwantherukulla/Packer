import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { Uploader } from "@/components/Uploader";

test("accepts a matching file and calls onFile", async () => {
  const onFile = vi.fn();
  render(<Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />);
  const input = screen.getByLabelText(/repository/i) as HTMLInputElement;
  await userEvent.upload(input, new File(["x"], "repo.zip", { type: "application/zip" }));
  expect(onFile).toHaveBeenCalledOnce();
  expect(screen.getByText("repo.zip")).toBeInTheDocument();
});

test("rejects a wrong extension without firing onFile", async () => {
  const onFile = vi.fn();
  render(<Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />);
  const input = screen.getByLabelText(/repository/i) as HTMLInputElement;
  // Bypass the native input `accept` filter (applyAccept) so the component's own
  // extension validation — the behavior under test — actually runs on the .txt.
  await userEvent.upload(input, new File(["x"], "notes.txt", { type: "text/plain" }), {
    applyAccept: false,
  });
  expect(onFile).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent(/\.zip/);
});
