import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { createJobProgressSocket } from "@/lib/ws";

class MockWS {
  static last: MockWS | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => this.onclose?.());
  constructor(public url: string) {
    MockWS.last = this;
  }
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", MockWS as unknown as typeof WebSocket);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

test("parses frames and reconnects on unexpected close", () => {
  const onEvent = vi.fn();
  const onClose = vi.fn();
  createJobProgressSocket(
    "j1",
    { onEvent, onClose },
    { baseDelayMs: 100, maxRetries: 2, url: (id) => `ws://x/ws/jobs/${id}` },
  );

  const sock = MockWS.last!;
  sock.onopen?.();
  sock.onmessage?.({ data: JSON.stringify({ step: "train", pct: 0.5, detail: "epoch 100" }) });
  expect(onEvent).toHaveBeenCalledWith({ step: "train", pct: 0.5, detail: "epoch 100" });

  sock.onclose?.(); // server dropped us
  expect(onClose).toHaveBeenCalledWith(true);
  vi.advanceTimersByTime(100); // backoff elapses → a new socket opens
  expect(MockWS.last).not.toBe(sock);
});

test("caller close() suppresses reconnect", () => {
  const handle = createJobProgressSocket("j1", { onEvent: vi.fn() }, { url: (id) => `ws://x/${id}` });
  handle.close();
  const after = MockWS.last;
  vi.advanceTimersByTime(10_000);
  expect(MockWS.last).toBe(after); // no new socket created
});
