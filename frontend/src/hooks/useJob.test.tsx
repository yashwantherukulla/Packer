import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useJob } from "@/hooks/useJob";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(async () => ({ data: { id: "j1", type: "detect", status: "succeeded" } })) },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

afterEach(() => vi.clearAllMocks());

test("useJob fetches and returns the job row", async () => {
  const { result } = renderHook(() => useJob("j1"), { wrapper });
  await waitFor(() => expect(result.current.data?.status).toBe("succeeded"));
});
