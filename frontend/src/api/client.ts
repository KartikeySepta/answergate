import { z } from "zod";

const baseUrl: string =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function getApiKey(): string | null {
  return localStorage.getItem("yt-ai-api-key");
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
  schema?: z.ZodType<T>
): Promise<T> {
  const { body, headers: customHeaders, ...rest } = options;

  const headers = new Headers(customHeaders);
  headers.set("Content-Type", "application/json");

  const apiKey = getApiKey();
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const fetchOptions: RequestInit = {
    ...rest,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const response = await fetch(`${baseUrl}${path}`, fetchOptions);

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text().catch(() => null);
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message, detail);
  }

  const data = await response.json();

  if (schema) {
    return schema.parse(data);
  }

  return data as T;
}
