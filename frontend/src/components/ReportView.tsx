import type { ReportBody } from "@/lib/report-view";
import { sectionsByType } from "@/lib/report-view";
import { BehaviorPanel } from "@/components/BehaviorPanel";
import { FindingsTable } from "@/components/FindingsTable";
import { SignalBreakdown } from "@/components/SignalBreakdown";
import { VerdictBadge } from "@/components/VerdictBadge";

export function ReportView({ report }: { report: ReportBody }) {
  const { signals, findings, behavior } = sectionsByType(report);
  return (
    <div className="space-y-4" data-testid={`report-${report.kind}`}>
      <VerdictBadge
        kind={report.kind}
        label={report.verdict.label}
        score={report.verdict.score}
        confidence={report.verdict.confidence}
      />

      {report.kind === "detect" ? (
        <SignalBreakdown signals={signals} />
      ) : (
        <>
          <FindingsTable findings={findings} />
          {behavior && <BehaviorPanel behavior={behavior} />}
        </>
      )}

      {report.limitations.length > 0 && (
        <section
          className="rounded border border-slate-300 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-800"
          data-testid="limitations"
        >
          <h3 className="font-medium">Limitations</h3>
          <ul className="list-disc pl-5">
            {report.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
