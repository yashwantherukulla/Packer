import { useParams } from "react-router-dom";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useJob, useArtifact, useReport } from "@/hooks/useJob";
import { useJobProgress } from "@/hooks/useJobProgress";

export function JobDetail() {
  const { id = "" } = useParams();
  const job = useJob(id);
  const progress = useJobProgress(id);
  const done = job.data?.status === "succeeded";
  const isPack = job.data?.type === "pack";
  const artifact = useArtifact(done && isPack ? (job.data?.result_ref ?? null) : null);
  const report = useReport(done && !isPack ? (job.data?.result_ref ?? null) : null);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Job {id}</h1>
      {!done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {done && isPack && artifact.data && (
        <PackResultCard
          metrics={artifact.data.metrics_json as unknown as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
        />
      )}
      {done && !isPack && report.data && <ReportView report={report.data} />}
    </div>
  );
}
