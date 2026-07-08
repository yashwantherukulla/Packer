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
      const { data, error } = await api.POST("/pack", {
        body: form as unknown as never,
        // Send the multipart FormData as-is (the generated body type is the
        // multipart object, so cast the passthrough serializer's return).
        bodySerializer: (b) => b as unknown as FormData,
      });
      if (error) throw error;
      return data as Job;
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
