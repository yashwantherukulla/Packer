export function parseResultRef(resultRef: string | null | undefined, kind: "artifact" | "report") {
  if (!resultRef) return null;
  const prefix = `${kind}:`;
  return resultRef.startsWith(prefix) ? resultRef.slice(prefix.length) : resultRef;
}

export function detectHrefForArtifact(artifactId: string) {
  return `/detect?model_ref=${encodeURIComponent(`artifact:${artifactId}`)}`;
}

export function isTerminalStatus(status: string | null | undefined) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}
