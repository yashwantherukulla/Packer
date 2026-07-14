import { useParams } from "react-router-dom";
import { JobFailureCard } from "@/components/JobFailureCard";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useJob, useArtifact, useReport } from "@/hooks/useJob";
import { useJobProgress } from "@/hooks/useJobProgress";
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
  const artifact = useArtifact(
    done && isPack ? parseResultRef(job.data?.result_ref, "artifact") : null,
  );
  const report = useReport(done && !isPack ? parseResultRef(job.data?.result_ref, "report") : null);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Job {id}</h1>
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
          metrics={artifact.data.metrics_json as unknown as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
          detectHref={detectHrefForArtifact(artifact.data.id)}
        />
      )}
      {done && !isPack && report.data && <ReportView report={report.data} />}
    </div>
  );
}
