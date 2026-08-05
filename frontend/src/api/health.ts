import { apiFetch } from "./client";
import { HealthSchema } from "./schemas";
import type { Health } from "./types";

export async function getHealth(): Promise<Health> {
  return apiFetch("/health", { method: "GET" }, HealthSchema);
}
