import { apiFetch } from "./client";
import { ChatResponseSchema, MessagesResponseSchema } from "./schemas";
import type { ChatResponse, Message, MessagesResponse } from "./types";

export async function sendMessage(
  workspaceId: string,
  question: string,
  history: Pick<Message, "role" | "content">[],
  mode?: string
): Promise<ChatResponse> {
  return apiFetch(
    "/chat",
    {
      method: "POST",
      body: { workspace_id: workspaceId, question, history, mode },
    },
    ChatResponseSchema
  );
}

/* Persisted conversation lives at /messages/{id}, not under /chat. */
export async function getMessages(workspaceId: string): Promise<MessagesResponse> {
  return apiFetch(
    `/messages/${encodeURIComponent(workspaceId)}`,
    { method: "GET" },
    MessagesResponseSchema
  );
}
