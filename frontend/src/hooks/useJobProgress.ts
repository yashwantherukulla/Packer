import { useEffect, useState } from "react";
import { createJobProgressSocket } from "@/lib/ws";
import { useJob } from "@/hooks/useJob";
import type { ProgressEvent } from "@/api/types";

export type ProgressView = { step: string; pct: number; detail: string | null };

export type LiveProgress = {
  event: ProgressView | null;
  connected: boolean;
  status?: string;
};

export function useJobProgress(jobId: string): LiveProgress {
  const [live, setLive] = useState<ProgressView | null>(null);
  const [connected, setConnected] = useState(false);

  // Query is the source of truth and drives the polling fallback on reconnect.
  const job = useJob(jobId);

  useEffect(() => {
    if (jobId === "") return;
    const socket = createJobProgressSocket(jobId, {
      onOpen: () => setConnected(true),
      onEvent: (e: ProgressEvent) => setLive({ step: e.step, pct: e.pct, detail: e.detail ?? null }),
      onClose: () => setConnected(false),
    });
    return () => socket.close();
  }, [jobId]);

  const row = job.data as
    | { progress_step?: string; progress_pct?: number; status?: string }
    | undefined;
  const fallback: ProgressView | null =
    !connected && row
      ? { step: row.progress_step ?? "", pct: row.progress_pct ?? 0, detail: null }
      : null;

  return {
    event: connected ? live : (fallback ?? live),
    connected,
    status: row?.status,
  };
}
