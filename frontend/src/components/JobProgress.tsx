export type JobProgressProps = {
  step: string;
  pct: number; // 0..1
  detail?: string | null;
  status?: string;
  connected: boolean;
};

export function JobProgress({ step, pct, detail, status, connected }: JobProgressProps) {
  const clamped = Math.min(Math.max(pct, 0), 1);
  const nowPct = Math.round(clamped * 100);
  const width = `${nowPct}%`;
  return (
    <div className="space-y-2" data-testid="job-progress">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{step || status || "queued"}</span>
        <span>{width}</span>
      </div>
      <div className="h-2 w-full rounded bg-slate-200 dark:bg-slate-700">
        <div
          className="h-2 rounded bg-blue-600 transition-all"
          style={{ width }}
          role="progressbar"
          aria-valuenow={nowPct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      {detail && <p className="text-xs text-slate-600 dark:text-slate-300">{detail}</p>}
      {!connected && (
        <p className="text-xs text-amber-700" role="status" data-testid="fallback-indicator">
          live stream lost — polling for updates
        </p>
      )}
    </div>
  );
}
