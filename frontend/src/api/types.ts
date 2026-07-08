import type { components } from "./schema";

// Wire types are re-exported (never re-declared) from the generated schema.
// Phase-4 model names: JobRecord / JobList / ReportResponse / ArtifactResponse
// (the plan's placeholder names Report/VerdictBlock/ArtifactMeta do not exist).
export type Job = components["schemas"]["JobRecord"];
export type JobList = components["schemas"]["JobList"];
export type Report = components["schemas"]["ReportResponse"];
export type Artifact = components["schemas"]["ArtifactResponse"];

// The WebSocket progress frame is published out-of-band (Redis pub/sub → the WS
// hub, see workers/progress.RedisProgress), so it is NOT part of the REST OpenAPI
// document and cannot be generated. It is the one hand-authored wire type; its
// shape mirrors RedisProgress.__call__: {"job_id", "step", "pct", "detail"}.
export type ProgressEvent = {
  job_id?: string;
  step: string;
  pct: number;
  detail?: string | null;
};
