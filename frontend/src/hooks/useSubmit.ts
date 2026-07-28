import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Job } from "@/api/types";

function useJobsInvalidator() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["jobs"] });
}

export function useSubmitPack() {
  const invalidate = useJobsInvalidator();
  return useMutation({
    mutationFn: async (form: FormData): Promise<Job> => {
      const resp = await fetch("/api/pack", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        throw new Error(await readHttpError(resp));
      }
      return (await resp.json()) as Job;
    },
    onSuccess: invalidate,
  });
}

function useModelRefSubmit(path: "/detect" | "/scan") {
  const invalidate = useJobsInvalidator();
  return useMutation({
    mutationFn: async (body: { model_ref: string }): Promise<Job> => {
      const { data, error } = await api.POST(path, { body });
      if (error) throw error;
      return data as Job;
    },
    onSuccess: invalidate,
  });
}

export const useSubmitDetect = () => useModelRefSubmit("/detect");
export const useSubmitScan = () => useModelRefSubmit("/scan");

async function readHttpError(resp: Response): Promise<string> {
  const raw = await resp.text();
  try {
    const parsed = JSON.parse(raw) as
      | { detail?: string | string[]; title?: string; code?: string }
      | undefined;
    if (parsed?.detail) {
      return Array.isArray(parsed.detail) ? parsed.detail.join("; ") : parsed.detail;
    }
    if (parsed?.title) {
      return parsed.title;
    }
  } catch {
    return raw;
  }
  return raw || `HTTP ${resp.status}`;
}
