import { apiFetch } from "./client";
import {
  WorkspaceListSchema,
  WorkspaceDetailSchema,
  DeleteResponseSchema,
} from "./schemas";
import type {
  WorkspaceList,
  WorkspaceDetail,
  DeleteResponse,
} from "./types";

export async function listWorkspaces(): Promise<WorkspaceList> {
  return apiFetch("/workspaces", { method: "GET" }, WorkspaceListSchema);
}

export async function getWorkspace(id: string): Promise<WorkspaceDetail> {
  return apiFetch(
    `/workspaces/${encodeURIComponent(id)}`,
    { method: "GET" },
    WorkspaceDetailSchema
  );
}

export async function deleteWorkspace(id: string): Promise<DeleteResponse> {
  return apiFetch(
    `/workspaces/${encodeURIComponent(id)}`,
    { method: "DELETE" },
    DeleteResponseSchema
  );
}
