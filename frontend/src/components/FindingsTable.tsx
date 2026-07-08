import { useState } from "react";
import type { Finding } from "@/lib/report-view";
import { severityTone, toneClasses } from "@/lib/verdict";

const RANK: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [desc, setDesc] = useState(true);
  const sorted = [...findings].sort((a, b) => {
    const d = (RANK[b.severity.toLowerCase()] ?? 0) - (RANK[a.severity.toLowerCase()] ?? 0);
    return desc ? d : -d;
  });
  return (
    <table className="w-full text-sm" data-testid="findings-table">
      <thead>
        <tr className="text-left">
          <th>
            <button type="button" onClick={() => setDesc((v) => !v)} data-testid="sort-severity">
              severity {desc ? "▼" : "▲"}
            </button>
          </th>
          <th>rule</th>
          <th>file</th>
          <th>line</th>
          <th>note</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((f, i) => (
          <tr key={`${f.file}:${f.rule}:${i}`} className="border-t">
            <td>
              <span className={`rounded border px-2 ${toneClasses[severityTone(f.severity)]}`}>
                {f.severity}
              </span>
            </td>
            <td className="font-mono">{f.rule}</td>
            <td className="font-mono">{f.file}</td>
            <td>{f.line ?? "—"}</td>
            <td>{f.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
