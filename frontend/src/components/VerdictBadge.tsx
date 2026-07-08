import { formatPct } from "@/lib/format";
import { riskTone, toneClasses, verdictTone } from "@/lib/verdict";

export type VerdictBadgeProps = {
  kind: "detect" | "scan";
  label: string;
  score: number;
  confidence: number;
};

export function VerdictBadge({ kind, label, score, confidence }: VerdictBadgeProps) {
  const tone = kind === "detect" ? verdictTone(label) : riskTone(label);
  return (
    <div
      className={`inline-flex flex-col rounded-lg border px-4 py-2 ${toneClasses[tone]}`}
      data-testid="verdict-badge"
    >
      <span className="text-lg font-semibold">{label}</span>
      <span className="text-xs">
        score {formatPct(score)} · confidence {formatPct(confidence)}
      </span>
    </div>
  );
}
