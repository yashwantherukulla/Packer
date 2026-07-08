import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useSubmitDetect } from "@/hooks/useSubmit";

// vi.mock is hoisted above module init, so the spy must be created via vi.hoisted
// to be referenceable inside the (also-hoisted) factory.
const { POST } = vi.hoisted(() => ({
  POST: vi.fn(async () => ({ data: { id: "job-9", type: "detect", status: "queued" } })),
}));
vi.mock("@/api/client", () => ({ api: { POST } }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

afterEach(() => vi.clearAllMocks());

test("useSubmitDetect posts model_ref and yields a job", async () => {
  const { result } = renderHook(() => useSubmitDetect(), { wrapper });
  act(() => result.current.mutate({ model_ref: "Qwen/Qwen2.5-0.5B" }));
  await waitFor(() => expect(result.current.data?.id).toBe("job-9"));
  expect(POST).toHaveBeenCalledWith("/detect", { body: { model_ref: "Qwen/Qwen2.5-0.5B" } });
});
