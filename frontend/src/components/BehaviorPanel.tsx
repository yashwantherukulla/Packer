import type { Behavior } from "@/lib/report-view";

function BehaviorList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-sm font-medium">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-slate-500">none</p>
      ) : (
        <ul className="list-disc pl-5 text-xs">
          {items.map((it, i) => (
            <li key={i} className="font-mono">
              {it}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BehaviorPanel({ behavior }: { behavior: Behavior }) {
  return (
    <div className="space-y-3" data-testid="behavior-panel">
      {behavior.disagreement && (
        <div
          className="rounded border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950"
          role="alert"
          data-testid="disagreement"
        >
          Static/dynamic disagreement: {behavior.disagreement}
        </div>
      )}
      <BehaviorList title="Syscalls" items={behavior.syscalls} />
      <BehaviorList title="Filesystem writes" items={behavior.fs_writes} />
      <BehaviorList title="Blocked network" items={behavior.blocked_net} />
    </div>
  );
}
