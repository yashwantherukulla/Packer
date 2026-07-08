import type { ProgressEvent } from "@/api/types";

export type ProgressHandlers = {
  onEvent: (e: ProgressEvent) => void;
  onOpen?: () => void;
  onClose?: (willReconnect: boolean) => void;
};

export type Socket = { close: () => void };

type Opts = { maxRetries?: number; baseDelayMs?: number; url?: (id: string) => string };

function defaultUrl(jobId: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/jobs/${jobId}`;
}

export function createJobProgressSocket(
  jobId: string,
  handlers: ProgressHandlers,
  opts: Opts = {},
): Socket {
  const maxRetries = opts.maxRetries ?? 5;
  const baseDelay = opts.baseDelayMs ?? 500;
  const makeUrl = opts.url ?? defaultUrl;

  let retries = 0;
  let closedByCaller = false;
  let ws: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    ws = new WebSocket(makeUrl(jobId));
    ws.onopen = () => {
      retries = 0;
      handlers.onOpen?.();
    };
    ws.onmessage = (msg: MessageEvent) => {
      try {
        handlers.onEvent(JSON.parse(String(msg.data)) as ProgressEvent);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      if (closedByCaller) return;
      const willReconnect = retries < maxRetries;
      handlers.onClose?.(willReconnect);
      if (willReconnect) {
        const delay = baseDelay * 2 ** retries;
        retries++;
        timer = setTimeout(connect, delay);
      }
    };
    ws.onerror = () => ws?.close();
  };

  connect();

  return {
    close: () => {
      closedByCaller = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    },
  };
}
