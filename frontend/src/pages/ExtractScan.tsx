import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { JobFailureCard } from "@/components/JobFailureCard";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useJob, useReport } from "@/hooks/useJob";
import { useSubmitScan } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { isTerminalStatus, parseResultRef } from "@/lib/result-ref";

export function ExtractScan() {
  const [searchParams] = useSearchParams();
  const presetModelRef = searchParams.get("model_ref") ?? "";
  const [modelRef, setModelRef] = useState(presetModelRef);
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
      ? "Reconstruction: byte-exact"
      : mode
        ? "Reconstruction: best-effort (blind)"
        : null;

  useEffect(() => {
    if (presetModelRef) {
      setModelRef(presetModelRef);
    }
  }, [presetModelRef]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Extract + Scan</h1>
      <div className="flex gap-2">
        <input
          value={modelRef}
          onChange={(e) => setModelRef(e.target.value)}
          placeholder="HF id, artifact id, or artifact:&lt;id&gt;"
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
      <p className="text-sm text-slate-600 dark:text-slate-300">
        Exact extraction and scan use the stored <code>.pak</code> when you pass{" "}
        <code>artifact:&lt;id&gt;</code> or a job artifact id. Other model refs fall back to
        best-effort reconstruction.
      </p>
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
