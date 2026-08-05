import { apiFetch } from "./client";
import {
  AddVideoResponseSchema,
  BatchResponseSchema,
  JobDetailSchema,
  JobListSchema,
} from "./schemas";
import type { AddVideoResponse, BatchResponse, JobDetail, JobList } from "./types";

export async function addVideo(
  url: string,
  workspaceId: string,
  engine?: string
): Promise<AddVideoResponse> {
  return apiFetch(
    "/add",
    { method: "POST", body: { url, workspace_id: workspaceId, engine } },
    AddVideoResponseSchema
  );
}

export async function addBatch(
  urls: string[],
  workspaceId: string,
  engine?: string
): Promise<BatchResponse> {
  return apiFetch(
    "/batch",
    { method: "POST", body: { urls, workspace_id: workspaceId, engine } },
    BatchResponseSchema
  );
}

export async function getJob(jobId: string, fullLog?: boolean): Promise<JobDetail> {
  // The backend flag is `full_log`; by default it returns only the log tail.
  const query = fullLog ? "?full_log=true" : "";
  return apiFetch(
    `/jobs/${encodeURIComponent(jobId)}${query}`,
    { method: "GET" },
    JobDetailSchema
  );
}

export async function listJobs(status?: string): Promise<JobList> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/jobs${query}`, { method: "GET" }, JobListSchema);
}

/* Cancellation is DELETE /jobs/{id} — there is no /cancel sub-resource. */
export async function cancelJob(jobId: string): Promise<{ status: string; job_id: string }> {
  return apiFetch(`/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" });
}
