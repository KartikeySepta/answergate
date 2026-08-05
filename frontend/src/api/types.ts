import { z } from "zod";
import {
  HealthSchema,
  AddVideoResponseSchema,
  BatchResponseSchema,
  JobDetailSchema,
  JobSummarySchema,
  JobListSchema,
  JobResultSchema,
  WorkspaceSchema,
  WorkspaceListSchema,
  WorkspaceDetailSchema,
  WorkspaceVideoSchema,
  ChatResponseSchema,
  ChatSourceSchema,
  MessageSchema,
  MessagesResponseSchema,
  ClaimSchema,
  ClaimsResponseSchema,
  ThemeSchema,
  ThemesResponseSchema,
  ReportResponseSchema,
  DeleteResponseSchema,
  EvidenceSchema,
  JobStatusEnum,
  ClaimTypeEnum,
  StanceEnum,
  RelationshipEnum,
} from "./schemas";

export type Health = z.infer<typeof HealthSchema>;
export type AddVideoResponse = z.infer<typeof AddVideoResponseSchema>;
export type BatchResponse = z.infer<typeof BatchResponseSchema>;
export type JobDetail = z.infer<typeof JobDetailSchema>;
export type JobSummary = z.infer<typeof JobSummarySchema>;
export type JobList = z.infer<typeof JobListSchema>;
export type JobResult = z.infer<typeof JobResultSchema>;
export type JobStatus = z.infer<typeof JobStatusEnum>;
export type Workspace = z.infer<typeof WorkspaceSchema>;
export type WorkspaceList = z.infer<typeof WorkspaceListSchema>;
export type WorkspaceDetail = z.infer<typeof WorkspaceDetailSchema>;
export type WorkspaceVideo = z.infer<typeof WorkspaceVideoSchema>;
export type ChatResponse = z.infer<typeof ChatResponseSchema>;
export type ChatSource = z.infer<typeof ChatSourceSchema>;
export type Message = z.infer<typeof MessageSchema>;
export type MessagesResponse = z.infer<typeof MessagesResponseSchema>;
export type Claim = z.infer<typeof ClaimSchema>;
export type ClaimsResponse = z.infer<typeof ClaimsResponseSchema>;
export type ClaimType = z.infer<typeof ClaimTypeEnum>;
export type Stance = z.infer<typeof StanceEnum>;
export type Evidence = z.infer<typeof EvidenceSchema>;
export type Theme = z.infer<typeof ThemeSchema>;
export type ThemesResponse = z.infer<typeof ThemesResponseSchema>;
export type Relationship = z.infer<typeof RelationshipEnum>;
export type ReportResponse = z.infer<typeof ReportResponseSchema>;
export type DeleteResponse = z.infer<typeof DeleteResponseSchema>;
