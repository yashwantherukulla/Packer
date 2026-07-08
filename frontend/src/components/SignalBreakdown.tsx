import { formatPct } from "@/lib/format";
import type { SignalItem } from "@/lib/report-view";

export function SignalBreakdown({ signals }: { signals: SignalItem[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="signal-breakdown">
      {signals.map((s) => (
        <div key={s.name} className="rounded-lg border p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium">{s.name}</span>
            <span className="text-sm">{formatPct(s.score)}</span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            confidence {formatPct(s.confidence)}
          </p>
          <dl className="mt-2 space-y-0.5 text-xs">
            {Object.entries(s.evidence).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}
