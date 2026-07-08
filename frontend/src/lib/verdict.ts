export type Tone = "danger" | "warn" | "ok" | "neutral";

export function verdictTone(label: string): Tone {
  switch (label.toUpperCase()) {
    case "MEMORIZED-CODE-LIKELY":
      return "danger";
    case "INCONCLUSIVE":
      return "warn";
    case "UNLIKELY":
      return "ok";
    default:
      return "neutral";
  }
}

export function riskTone(label: string): Tone {
  switch (label.toLowerCase()) {
    case "malicious":
      return "danger";
    case "suspicious":
      return "warn";
    case "benign":
      return "ok";
    default:
      return "neutral";
  }
}

export function severityTone(sev: string): Tone {
  switch (sev.toLowerCase()) {
    case "critical":
    case "high":
      return "danger";
    case "medium":
      return "warn";
    case "low":
      return "ok";
    default:
      return "neutral";
  }
}

export const toneClasses: Record<Tone, string> = {
  danger:
    "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-100 dark:border-red-800",
  warn: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-100 dark:border-amber-800",
  ok: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-100 dark:border-emerald-800",
  neutral:
    "bg-slate-100 text-slate-900 border-slate-300 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700",
};
