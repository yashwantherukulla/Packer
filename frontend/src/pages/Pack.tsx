import { useState } from "react";
import { Uploader } from "@/components/Uploader";
import { JobProgress } from "@/components/JobProgress";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useSubmitPack } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useArtifact } from "@/hooks/useJob";

export function Pack() {
  const [epochs, setEpochs] = useState(200);
  const submit = useSubmitPack();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const done = progress.status === "succeeded";
  const artifact = useArtifact(done ? jobId : null);

  const onFile = (file: File) => {
    const form = new FormData();
    form.append("repo", file);
    form.append("epochs", String(epochs));
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
      {jobId && !done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {done && artifact.data && (
        <PackResultCard
          metrics={artifact.data.metrics_json as unknown as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
        />
      )}
    </div>
  );
}
