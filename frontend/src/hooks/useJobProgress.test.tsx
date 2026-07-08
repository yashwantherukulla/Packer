import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useJobProgress } from "@/hooks/useJobProgress";

let handlers: { onOpen?: () => void; onEvent: (e: unknown) => void; onClose?: (r: boolean) => void };
const close = vi.fn();
vi.mock("@/lib/ws", () => ({
  createJobProgressSocket: (_id: string, h: typeof handlers) => {
    handlers = h;
    return { close };
  },
}));
vi.mock("@/hooks/useJob", () => ({
  useJob: () => ({ data: { status: "running", progress_step: "train", progress_pct: 0.2 } }),
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);
afterEach(() => vi.clearAllMocks());

test("live WS event wins; on close it falls back to the polled job row", () => {
  const { result } = renderHook(() => useJobProgress("j1"), { wrapper });

  act(() => handlers.onOpen?.());
  act(() => handlers.onEvent({ step: "train", pct: 0.8, detail: "epoch 160" }));
  expect(result.current.connected).toBe(true);
  expect(result.current.event).toEqual({ step: "train", pct: 0.8, detail: "epoch 160" });

  act(() => handlers.onClose?.(true));
  expect(result.current.connected).toBe(false);
  expect(result.current.event).toEqual({ step: "train", pct: 0.2, detail: null }); // from Query
});
