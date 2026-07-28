import { useEffect, useState } from "react";

function readStoredJobId(key: string) {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(key);
}

function writeStoredJobId(key: string, jobId: string | null) {
  if (typeof window === "undefined") return;
  if (jobId) {
    window.sessionStorage.setItem(key, jobId);
    return;
  }
  window.sessionStorage.removeItem(key);
}

export function useSessionJobId(key: string, latestJobId: string | null | undefined) {
  const [jobId, setJobId] = useState<string | null>(() => readStoredJobId(key));

  useEffect(() => {
    if (!latestJobId) return;
    setJobId(latestJobId);
    writeStoredJobId(key, latestJobId);
  }, [key, latestJobId]);

  const persistJobId = (nextJobId: string | null) => {
    setJobId(nextJobId);
    writeStoredJobId(key, nextJobId);
  };

  return { jobId, setJobId: persistJobId };
}
