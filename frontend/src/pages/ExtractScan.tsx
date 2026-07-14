import { useState } from "react";
import { JobFailureCard } from "@/components/JobFailureCard";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useJob, useReport } from "@/hooks/useJob";
import { useSubmitScan } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { isTerminalStatus, parseResultRef } from "@/lib/result-ref";

export function ExtractScan() {
  const [modelRef, setModelRef] = useState("");
  const submit = useSubmitScan();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const job = useJob(jobId ?? "");
  const status = job.data?.status ?? progress.status;
  const done = status === "succeeded";
  const failed = status === "failed";
  const active = !isTerminalStatus(status);
  const reportId = parseResultRef(job.data?.result_ref, "report");
  const report = useReport(done ? reportId : null);

  const mode = (report.data?.evidence as { extraction?: { mode?: string } } | undefined)?.extraction
    ?.mode;
  const banner =
    mode === "exact"
      ? "Reconstruction: byte-exact ✓"
      : mode
        ? "Reconstruction: best-effort (blind)"
        : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Extract + Scan</h1>
      <div className="flex gap-2">
        <input
          value={modelRef}
          onChange={(e) => setModelRef(e.target.value)}
          placeholder="model_ref (add an artifact id for exact mode)"
          data-testid="model-ref"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="button"
          onClick={() => submit.mutate({ model_ref: modelRef })}
          className="rounded bg-blue-600 px-4 text-white"
          data-testid="submit"
        >
          Run
        </button>
      </div>
      {jobId && active && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={status}
          connected={progress.connected}
        />
      )}
      {failed && <JobFailureCard error={job.data?.error} errorCode={job.data?.error_code} />}
      {banner && (
        <p className="text-sm font-medium" data-testid="reconstruction">
          {banner}
        </p>
      )}
      {report.data && <ReportView report={report.data} />}
    </div>
  );
}
