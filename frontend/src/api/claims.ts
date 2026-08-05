import { apiFetch } from "./client";
import {
  ClaimsResponseSchema,
  ThemesResponseSchema,
  ReportResponseSchema,
} from "./schemas";
import type { ClaimsResponse, ThemesResponse, ReportResponse } from "./types";

/*
 * Path note: these are top-level resources on the backend (/claims/{id}), not
 * nested under /workspaces. Worth stating because the nested form reads more
 * RESTful and is easy to "fix" into a 404.
 */

export async function getClaims(
  workspaceId: string,
  limit?: number,
  offset?: number
): Promise<ClaimsResponse> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set("limit", String(limit));
  if (offset !== undefined) params.set("offset", String(offset));
  const query = params.toString();
  return apiFetch(
    `/claims/${encodeURIComponent(workspaceId)}${query ? `?${query}` : ""}`,
    { method: "GET" },
    ClaimsResponseSchema
  );
}

export async function getThemes(workspaceId: string): Promise<ThemesResponse> {
  return apiFetch(
    `/themes/${encodeURIComponent(workspaceId)}`,
    { method: "GET" },
    ThemesResponseSchema
  );
}

export async function getReport(workspaceId: string): Promise<ReportResponse> {
  return apiFetch(
    `/report/${encodeURIComponent(workspaceId)}`,
    { method: "GET" },
    ReportResponseSchema
  );
}
