import { z } from "zod";

// --- Health ---
export const HealthSchema = z.object({
  status: z.string(),
  auth_required: z.boolean(),
  queue_depth: z.number(),
});

// --- Jobs ---
export const AddVideoResponseSchema = z.object({
  job_id: z.string(),
  status: z.string(),
  workspace_id: z.string(),
  queue_position: z.number(),
  poll: z.string(),
});

export const BatchResponseSchema = z.object({
  workspace_id: z.string(),
  job_ids: z.array(z.string()),
  count: z.number(),
  poll: z.string(),
});

export const JobStatusEnum = z.enum([
  "queued",
  "running",
  "done",
  "failed",
  "cancelled",
  "interrupted",
]);

export const JobResultSchema = z.object({
  workspace_id: z.string(),
  videos: z.number(),
  chunks: z.number(),
  claims: z.number(),
  has_report: z.boolean(),
});

export const JobDetailSchema = z.object({
  job_id: z.string(),
  kind: z.string(),
  params: z.object({
    url: z.string(),
    workspace_id: z.string(),
    engine: z.string(),
  }),
  status: JobStatusEnum,
  steps: z.array(z.string()),
  step_index: z.number(),
  current_step: z.string().nullable(),
  progress: z.number(),
  created_at: z.number(),
  started_at: z.number().nullable(),
  finished_at: z.number().nullable(),
  duration_seconds: z.number().nullable(),
  error: z.string().nullable(),
  result: JobResultSchema.nullable(),
  log: z.array(z.string()),
});

export const JobSummarySchema = JobDetailSchema.omit({ log: true });

export const JobListSchema = z.object({
  queue_depth: z.number(),
  jobs: z.array(JobSummarySchema),
});

// --- Workspaces ---
export const WorkspaceSchema = z.object({
  id: z.string(),
  videos: z.number(),
  claims: z.number(),
  has_report: z.boolean(),
});

export const WorkspaceListSchema = z.object({
  workspaces: z.array(WorkspaceSchema),
});

export const WorkspaceVideoSchema = z.object({
  video_id: z.string(),
  title: z.string().nullable(),
  channel: z.string().nullable(),
  duration_seconds: z.number().nullable(),
});

export const WorkspaceDetailSchema = z.object({
  workspace_id: z.string(),
  videos: z.array(WorkspaceVideoSchema),
  claim_count: z.number(),
  theme_count: z.number(),
  has_report: z.boolean(),
});

// --- Chat ---
export const ChatSourceSchema = z.object({
  video_title: z.string(),
  timestamp: z.string(),
});

export const ChatResponseSchema = z.object({
  answer: z.string(),
  sources: z.record(z.string(), ChatSourceSchema),
  citations_valid: z.boolean(),
  cited_count: z.number(),
  mode: z.string(),
  verified: z.boolean(),
  caveat: z.string().nullable(),
});

export const MessageSchema = z.object({
  role: z.string(),
  content: z.string(),
  mode: z.string(),
});

export const MessagesResponseSchema = z.object({
  workspace_id: z.string(),
  messages: z.array(MessageSchema),
});

// --- Claims ---
export const ClaimTypeEnum = z.enum([
  "recommendation",
  "opinion",
  "fact",
  "prediction",
  "warning",
]);

export const StanceEnum = z.enum(["support", "oppose", "neutral", "mixed"]);

export const EvidenceSchema = z.object({
  chunk_id: z.string(),
  evidence_text: z.string(),
});

export const ClaimSchema = z.object({
  claim_id: z.string(),
  video_id: z.string(),
  claim: z.string(),
  claim_type: ClaimTypeEnum,
  stance: StanceEnum,
  evidence: z.array(EvidenceSchema),
  topics: z.array(z.string()),
  cluster_id: z.string().nullable(),
});

export const ClaimsResponseSchema = z.object({
  workspace_id: z.string(),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
  claims: z.array(ClaimSchema),
});

// --- Themes ---
export const RelationshipEnum = z.enum([
  "agreement",
  "partial_agreement",
  "contradiction",
  "different_context",
  "independent",
  "related",
]);

export const ThemeSchema = z.object({
  theme_id: z.string(),
  member_claim_ids: z.array(z.string()),
  videos: z.array(z.string()),
  cosine: z.number(),
  relationship: RelationshipEnum,
  synthesis_note: z.string(),
});

export const ThemesResponseSchema = z.object({
  workspace_id: z.string(),
  themes: z.array(ThemeSchema),
});

// --- Report ---
export const ReportResponseSchema = z.object({
  workspace_id: z.string(),
  markdown: z.string(),
});

// --- Delete ---
export const DeleteResponseSchema = z.object({
  status: z.string(),
  workspace_id: z.string(),
  vectors_removed: z.number(),
});
