import { formatBytes, formatRatio } from "@/lib/format";

export type ArtifactMetrics = {
  original_bytes: number;
  gzip_bytes: number;
  artifact_bytes: number;
  compression_ratio_vs_original: number | null;
};

export function PackResultCard({
  metrics,
  downloadHref,
}: {
  metrics: ArtifactMetrics;
  downloadHref: string;
}) {
  const rows: [string, string][] = [
    ["Original", formatBytes(metrics.original_bytes)],
    ["gzip", formatBytes(metrics.gzip_bytes)],
    ["Artifact (.pak)", formatBytes(metrics.artifact_bytes)],
  ];
  return (
    <div className="rounded-lg border p-4" data-testid="pack-result">
      <h3 className="font-semibold">Artifact ready</h3>
      <table className="mt-2 w-full text-sm">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-t">
              <td className="py-1">{k}</td>
              <td className="py-1 text-right font-mono">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {metrics.compression_ratio_vs_original != null && (
        <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">
          Artifact is {formatRatio(metrics.compression_ratio_vs_original)} the original — Packer is a
          memorization demo, not a compressor.
        </p>
      )}
      <a
        href={downloadHref}
        className="mt-3 inline-block rounded bg-blue-600 px-3 py-1.5 text-white"
        data-testid="download"
      >
        Download .pak
      </a>
    </div>
  );
}
