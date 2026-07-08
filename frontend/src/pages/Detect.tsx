import { useState } from "react";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useSubmitDetect } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useReport } from "@/hooks/useJob";

export function Detect() {
  const [modelRef, setModelRef] = useState("");
  const submit = useSubmitDetect();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const done = progress.status === "succeeded";
  const report = useReport(done ? (submit.data?.result_ref ?? null) : null);

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
      {jobId && !done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {report.data && <ReportView report={report.data} />}
    </div>
  );
}
