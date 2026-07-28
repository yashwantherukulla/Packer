import { Link } from "react-router-dom";
import { formatBytes, formatRatio } from "@/lib/format";

export type ArtifactMetrics = {
  original_bytes: number;
  gzip_bytes: number;
  artifact_bytes: number;
  compression_ratio_vs_original: number | null;
};

export function PackResultCard({
  artifactId,
  metrics,
  downloadHref,
  detectHref,
}: {
  artifactId?: string;
  metrics: ArtifactMetrics;
  downloadHref: string;
  detectHref?: string;
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
      {artifactId && (
        <label className="mt-3 block text-sm">
          <span className="block text-xs font-medium uppercase tracking-wide text-slate-500">
            Artifact id
          </span>
          <input
            readOnly
            value={artifactId}
            className="mt-1 w-full rounded border bg-slate-50 px-3 py-2 font-mono text-sm"
            data-testid="artifact-id"
          />
        </label>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href={downloadHref}
          download
          className="inline-block rounded bg-blue-600 px-3 py-1.5 text-white"
          data-testid="download"
        >
          Download .pak
        </a>
        {detectHref && (
          <Link
            to={detectHref}
            className="inline-block rounded border border-slate-300 px-3 py-1.5 text-slate-900"
            data-testid="detect-from-pack"
          >
            Open in Detect
          </Link>
        )}
      </div>
    </div>
  );
}
