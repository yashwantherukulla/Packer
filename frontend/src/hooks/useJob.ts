import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Artifact, Job, Report } from "@/api/types";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    enabled: id !== "",
    queryFn: async (): Promise<Job> => {
      const { data, error } = await api.GET("/jobs/{job_id}", { params: { path: { job_id: id } } });
      if (error) throw error;
      return data as Job;
    },
    // Poll while active; this is the source of truth the WS layer falls back to.
    refetchInterval: (q) =>
      TERMINAL.has((q.state.data as Job | undefined)?.status ?? "") ? false : 1500,
  });
}

export function useJobs(filters: { status?: string; type?: string } = {}) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: async (): Promise<Job[]> => {
      const { data, error } = await api.GET("/jobs", { params: { query: filters } });
      if (error) throw error;
      // GET /jobs returns a JobList wrapper ({ jobs: [...] }), not a bare array.
      return data?.jobs ?? [];
    },
  });
}

export function useReport(id: string | null) {
  return useQuery({
    queryKey: ["report", id],
    enabled: id != null,
    queryFn: async (): Promise<Report> => {
      const { data, error } = await api.GET("/reports/{report_id}", {
        params: { path: { report_id: id! } },
      });
      if (error) throw error;
      return data as Report;
    },
  });
}

export function useArtifact(id: string | null) {
  return useQuery({
    queryKey: ["artifact", id],
    enabled: id != null,
    queryFn: async (): Promise<Artifact> => {
      const { data, error } = await api.GET("/artifacts/{artifact_id}", {
        params: { path: { artifact_id: id! } },
      });
      if (error) throw error;
      return data as Artifact;
    },
  });
}
