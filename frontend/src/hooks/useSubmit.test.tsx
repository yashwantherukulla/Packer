import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useSubmitDetect, useSubmitPack } from "@/hooks/useSubmit";

// vi.mock is hoisted above module init, so the spy must be created via vi.hoisted
// to be referenceable inside the (also-hoisted) factory.
const { POST, fetchMock } = vi.hoisted(() => ({
  POST: vi.fn(async () => ({ data: { id: "job-9", type: "detect", status: "queued" } })),
  fetchMock: vi.fn(async () => new Response(JSON.stringify({ id: "job-7", type: "pack", status: "queued" }), { status: 202, headers: { "content-type": "application/json" } })),
}));
vi.mock("@/api/client", () => ({ api: { POST } }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

test("useSubmitDetect posts model_ref and yields a job", async () => {
  const { result } = renderHook(() => useSubmitDetect(), { wrapper });
  act(() => result.current.mutate({ model_ref: "Qwen/Qwen2.5-0.5B" }));
  await waitFor(() => expect(result.current.data?.id).toBe("job-9"));
  expect(POST).toHaveBeenCalledWith("/detect", { body: { model_ref: "Qwen/Qwen2.5-0.5B" } });
});

test("useSubmitPack sends a native multipart request and yields a job", async () => {
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useSubmitPack(), { wrapper });
  const form = new FormData();
  form.append("file", new File(["zip"], "repo.zip", { type: "application/zip" }));
  act(() => result.current.mutate(form));
  await waitFor(() => expect(result.current.data?.id).toBe("job-7"));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/pack",
    expect.objectContaining({ method: "POST", body: form }),
  );
});
