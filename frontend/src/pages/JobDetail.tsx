import { useParams } from "react-router-dom";
import { JobFailureCard } from "@/components/JobFailureCard";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useJob, useArtifact, useReport } from "@/hooks/useJob";
import { useJobProgress } from "@/hooks/useJobProgress";
import { formatTimestamp } from "@/lib/datetime";
import { detectHrefForArtifact } from "@/lib/result-ref";
import { isTerminalStatus, parseResultRef } from "@/lib/result-ref";

export function JobDetail() {
  const { id = "" } = useParams();
  const job = useJob(id);
  const progress = useJobProgress(id);
  const status = job.data?.status ?? progress.status;
  const done = status === "succeeded";
  const failed = status === "failed";
  const active = !isTerminalStatus(status);
  const isPack = job.data?.type === "pack";
  const resultRef = job.data?.result_ref ?? null;
  const artifactId = isPack ? parseResultRef(resultRef, "artifact") : null;
  const reportId = !isPack ? parseResultRef(resultRef, "report") : null;
  const artifact = useArtifact(done && isPack ? artifactId : null);
  const report = useReport(done && !isPack ? reportId : null);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Job {id}</h1>
      {job.data && (
        <dl className="grid gap-3 rounded-lg border p-4 text-sm sm:grid-cols-2" data-testid="job-meta">
          <div>
            <dt className="text-slate-500">Type</dt>
            <dd className="font-medium">{job.data.type}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Status</dt>
            <dd className="font-medium">{job.data.status}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Created</dt>
            <dd className="font-mono">{formatTimestamp(job.data.created_at)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Finished</dt>
            <dd className="font-mono">{formatTimestamp(job.data.finished_at)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-slate-500">Result ref</dt>
            <dd className="break-all font-mono">{resultRef ?? "pending"}</dd>
          </div>
        </dl>
      )}
      {active && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={status}
          connected={progress.connected}
        />
      )}
      {failed && <JobFailureCard error={job.data?.error} errorCode={job.data?.error_code} />}
      {done && isPack && artifact.data && (
        <PackResultCard
          artifactId={artifactId ?? artifact.data.id}
          metrics={artifact.data.metrics_json as unknown as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
          detectHref={detectHrefForArtifact(artifact.data.id)}
        />
      )}
      {done && !isPack && report.data && <ReportView report={report.data} />}
    </div>
  );
}
