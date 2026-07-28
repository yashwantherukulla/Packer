import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { JobFailureCard } from "@/components/JobFailureCard";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useJob, useReport } from "@/hooks/useJob";
import { useSubmitDetect } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useSessionJobId } from "@/hooks/useSessionJob";
import { isTerminalStatus, parseResultRef } from "@/lib/result-ref";

export function Detect() {
  const [searchParams] = useSearchParams();
  const presetModelRef = searchParams.get("model_ref") ?? "";
  const [modelRef, setModelRef] = useState(presetModelRef);
  const submit = useSubmitDetect();
  const { jobId } = useSessionJobId("detect:last-job-id", submit.data?.id);
  const progress = useJobProgress(jobId ?? "");
  const job = useJob(jobId ?? "");
  const status = job.data?.status ?? progress.status;
  const done = status === "succeeded";
  const failed = status === "failed";
  const active = !isTerminalStatus(status);
  const reportId = parseResultRef(job.data?.result_ref, "report");
  const report = useReport(done ? reportId : null);

  useEffect(() => {
    if (presetModelRef) {
      setModelRef(presetModelRef);
    }
  }, [presetModelRef]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Detect memorized code</h1>
      <div className="flex gap-2">
        <input
          value={modelRef}
          onChange={(e) => setModelRef(e.target.value)}
          placeholder="HF id, uploaded id, or artifact id"
          data-testid="model-ref"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="button"
          onClick={() => submit.mutate({ model_ref: modelRef })}
          className="rounded bg-blue-600 px-4 text-white"
          data-testid="submit"
        >
          Detect
        </button>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-300">
        HF ids are downloaded from the Hugging Face Hub, local paths are read from disk, and
        <code>artifact:&lt;id&gt;</code> resolves to the stored <code>.pak</code> for exact
        artifact-based detection.
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
      {report.data && <ReportView report={report.data} />}
    </div>
  );
}
