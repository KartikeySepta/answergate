import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatDistanceToNowStrict } from "date-fns";
import { useJobs } from "@/hooks/useJobs";
import { JobStatusBadge } from "@/components/job/JobStatusBadge";
import { StepTrackMini } from "@/components/job/StepChecklist";
import {
  EmptyState,
  GutterList,
  GutterRow,
  MicroLabel,
  Mono,
  PageHeader,
  Segmented,
} from "@/components/ui/primitives";
import type { JobStatus } from "@/api/types";

type Filter = "all" | JobStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "running", label: "Running" },
  { value: "queued", label: "Queued" },
  { value: "done", label: "Done" },
  { value: "failed", label: "Failed" },
];

export function JobHistoryPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const { data, isLoading } = useJobs(filter === "all" ? undefined : filter);

  const jobs = data?.jobs ?? [];
  const depth = data?.queue_depth ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="step 02"
        title="Processing"
        description={
          depth > 0
            ? `${depth} waiting. Jobs run one at a time — the pipeline shares a single index and model, so serialising them avoids corruption.`
            : "Every source you add becomes a job here."
        }
      />

      <div className="mb-5">
        <Segmented size="sm" value={filter} onChange={setFilter} options={FILTERS} />
      </div>

      {isLoading ? (
        <div className="space-y-px">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded bg-card/40" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          title={filter === "all" ? "no jobs yet" : `nothing ${filter}`}
          description={
            filter === "all"
              ? "Add a source and its progress will show up here."
              : undefined
          }
          action={filter === "all" ? { label: "Add a source", to: "/" } : undefined}
        />
      ) : (
        <GutterList>
          {jobs.map((job, i) => (
            <GutterRow
              key={job.job_id}
              n={i + 1}
              onClick={() => navigate(`/jobs/${job.job_id}`)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2.5">
                    <span className="truncate font-mono text-[13px] text-foreground">
                      {job.params.workspace_id}
                    </span>
                    <JobStatusBadge status={job.status} />
                  </div>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground/60">
                    {job.params.url}
                  </p>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <StepTrackMini
                    steps={job.steps}
                    stepIndex={job.step_index}
                    status={job.status}
                  />
                  <div className="flex items-center gap-2.5">
                    {job.status === "running" && (
                      <span className="tabular font-mono text-[10px] text-primary">
                        {job.progress}%
                      </span>
                    )}
                    <Mono dim>{relative(job.created_at)}</Mono>
                    {job.duration_seconds != null && (
                      <Mono dim>{fmtDur(job.duration_seconds)}</Mono>
                    )}
                  </div>
                </div>
              </div>
            </GutterRow>
          ))}
        </GutterList>
      )}

      {jobs.length > 0 && (
        <MicroLabel className="mt-4 block">
          {jobs.length} shown · finished jobs are kept 24h
        </MicroLabel>
      )}
    </div>
  );
}

function relative(unixSeconds: number): string {
  try {
    return formatDistanceToNowStrict(new Date(unixSeconds * 1000), { addSuffix: false });
  } catch {
    return "—";
  }
}

function fmtDur(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h${m % 60}m`;
}
