import type { Report } from "@/api/types";

// ---------------------------------------------------------------------------
// Presentational view models over the opaque wire report payload.
//
// The generated wire type `ReportResponse` (re-exported as `Report`) is
// `{ id, job_id, kind, report: { [k: string]: unknown } }` — the engine report
// body (verdict/sections/evidence/limitations) is an opaque `dict` on the wire
// with no OpenAPI schema (SYSTEM-DESIGN §11, the sanctioned `dict` carve-out).
// These are the only hand-authored types allowed: presentational view models
// narrowing that opaque body for rendering.
// ---------------------------------------------------------------------------

export type Verdict = { label: string; score: number; confidence: number };
export type ReportSection = { type?: string; title?: string; data?: unknown };

/** Flat, render-ready view model over the opaque wire `report` body dict. */
export type ReportBody = {
  kind: "detect" | "scan";
  schema_version?: string;
  verdict: Verdict;
  sections: ReportSection[];
  evidence: Record<string, unknown>;
  limitations: string[];
};

export type SignalItem = {
  name: string;
  score: number;
  confidence: number;
  evidence: Record<string, unknown>;
};
export type Finding = { severity: string; rule: string; file: string; line: number | null; note: string };
export type Behavior = {
  syscalls: string[];
  fs_writes: string[];
  blocked_net: string[];
  disagreement?: string | null;
};

/**
 * Flatten the wire `ReportResponse` into the presentational `ReportBody`.
 * `kind` is promoted to the top of the wire response; the rest of the body
 * lives inside the opaque `report` dict.
 */
export function toReportBody(res: Report): ReportBody {
  const body = (res.report ?? {}) as unknown as Partial<ReportBody>;
  return {
    kind: (res.kind as "detect" | "scan") ?? body.kind ?? "detect",
    schema_version: body.schema_version,
    verdict: body.verdict ?? { label: "", score: 0, confidence: 0 },
    sections: body.sections ?? [],
    evidence: body.evidence ?? {},
    limitations: body.limitations ?? [],
  };
}

export function sectionsByType(report: ReportBody): {
  signals: SignalItem[];
  findings: Finding[];
  behavior: Behavior | null;
} {
  const sections = report.sections;
  const of = (t: string) => sections.filter((s) => s.type === t);
  const signals = of("signals").flatMap(
    (s) => (s.data as { signals?: SignalItem[] } | undefined)?.signals ?? [],
  );
  const findings = of("findings").flatMap(
    (s) => (s.data as { findings?: Finding[] } | undefined)?.findings ?? [],
  );
  const behavior = (of("behavior")[0]?.data as Behavior | undefined) ?? null;
  return { signals, findings, behavior };
}
