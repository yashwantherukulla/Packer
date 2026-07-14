import { useState } from "react";
import { JobFailureCard } from "@/components/JobFailureCard";
import { Uploader } from "@/components/Uploader";
import { JobProgress } from "@/components/JobProgress";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useJob, useArtifact } from "@/hooks/useJob";
import { useSubmitPack } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { detectHrefForArtifact } from "@/lib/result-ref";
import { isTerminalStatus, parseResultRef } from "@/lib/result-ref";

export function Pack() {
  const [epochs, setEpochs] = useState(200);
  const submit = useSubmitPack();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const job = useJob(jobId ?? "");
  const status = job.data?.status ?? progress.status;
  const done = status === "succeeded";
  const failed = status === "failed";
  const active = !isTerminalStatus(status);
  const artifactId = parseResultRef(job.data?.result_ref, "artifact");
  const artifact = useArtifact(done ? artifactId : null);

  const onFile = (file: File) => {
    const form = new FormData();
    // The API's POST /pack expects the multipart field named "file" (see
    // packer.api.routers.pack.submit_pack); "repo" yields a 422. Epochs are set by
    // server-side Hydra config and currently ignored by the endpoint.
    form.append("file", file);
    submit.mutate(form);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Pack a repository</h1>
      <Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />
      <label className="block text-sm">
        Epochs
        <input
          type="number"
          min={1}
          value={epochs}
          onChange={(e) => setEpochs(Number(e.target.value))}
          className="ml-2 w-24 rounded border px-2"
          data-testid="epochs"
        />
      </label>
      {submit.isError && (
        <p className="text-sm text-red-700" role="alert">
          Submission failed.
        </p>
      )}
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
      {done && artifact.data && (
        <PackResultCard
          metrics={artifact.data.metrics_json as unknown as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
          detectHref={detectHrefForArtifact(artifact.data.id)}
        />
      )}
    </div>
  );
}
