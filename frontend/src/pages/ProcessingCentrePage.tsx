import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Ban,
  AlertTriangle,
  Filter,
} from "lucide-react";
import { useJobs, useCancelJob } from "@/hooks/useJobs";
import { cn } from "@/lib/utils";
import type { JobSummary } from "@/api/types";

type StatusFilter = "all" | "running" | "queued" | "done" | "failed";

export function ProcessingCentrePage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const { data, isLoading } = useJobs();
  const cancelJob = useCancelJob();

  const jobs = data?.jobs ?? [];
  const filtered =
    filter === "all"
      ? jobs
      : jobs.filter((j) => {
          if (filter === "running") return j.status === "running" || j.status === "queued";
          return j.status === filter;
        });

  const activeCount = jobs.filter(
    (j) => j.status === "running" || j.status === "queued"
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Processing Centre
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {activeCount > 0
              ? `${activeCount} job${activeCount !== 1 ? "s" : ""} currently active`
              : "All jobs idle"}
            {data?.queue_depth ? ` · ${data.queue_depth} in queue` : ""}
          </p>
        </div>
        <Link
          to="/research/new"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90"
        >
          Add source
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        {(["all", "running", "done", "failed"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors",
              filter === f
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground"
            )}
          >
            {f === "running" ? "Active" : f}
          </button>
        ))}
      </div>

      {/* Jobs list */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl border border-border bg-card" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-12 text-center">
          <Clock className="mx-auto h-8 w-8 text-muted-foreground/50" />
          <p className="mt-3 text-sm text-muted-foreground">
            {filter === "all" ? "No jobs yet. Add a YouTube source to start." : `No ${filter} jobs.`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((job) => (
            <JobRow key={job.job_id} job={job} onCancel={cancelJob} />
          ))}
        </div>
      )}
    </div>
  );
}

function JobRow({
  job,
  onCancel,
}: {
  job: JobSummary;
  onCancel: ReturnType<typeof useCancelJob>;
}) {
  const isActive = job.status === "running" || job.status === "queued";
  const elapsed = job.duration_seconds
    ? formatDuration(job.duration_seconds)
    : job.started_at
      ? formatDuration(Date.now() / 1000 - job.started_at)
      : null;

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/20">
      <JobIcon status={job.status} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={`/processing/${job.job_id}`}
            className="truncate text-sm font-medium text-foreground hover:text-primary"
          >
            {job.params.workspace_id}
          </Link>
          <StatusBadge status={job.status} />
        </div>
        <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
          {job.params.url}
        </p>
        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
          {job.current_step && isActive && (
            <span>{job.current_step}</span>
          )}
          {elapsed && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {elapsed}
            </span>
          )}
          {job.params.engine && (
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px]">
              {job.params.engine}
            </span>
          )}
        </div>
      </div>

      {/* Progress */}
      {isActive && (
        <div className="hidden w-24 sm:block">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <p className="mt-1 text-right text-[10px] tabular text-muted-foreground">
            {job.progress}%
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        {isActive && (
          <button
            onClick={(e) => {
              e.preventDefault();
              onCancel.mutate(job.job_id, {
                onSuccess: () => toast.success("Cancelled"),
                onError: (err) => toast.error(err.message),
              });
            }}
            disabled={onCancel.isPending}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-destructive/5 hover:text-destructive"
            aria-label="Cancel job"
          >
            <Ban className="h-4 w-4" />
          </button>
        )}
        {job.status === "done" && job.result && (
          <Link
            to={`/research/${job.params.workspace_id}`}
            className="rounded-lg border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
          >
            Open
          </Link>
        )}
      </div>
    </div>
  );
}

function JobIcon({ status }: { status: string }) {
  const base = "flex h-9 w-9 items-center justify-center rounded-full";
  if (status === "running")
    return (
      <div className={cn(base, "bg-primary/10")}>
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
      </div>
    );
  if (status === "queued")
    return (
      <div className={cn(base, "bg-secondary")}>
        <Clock className="h-4 w-4 text-muted-foreground" />
      </div>
    );
  if (status === "done")
    return (
      <div className={cn(base, "bg-success/10")}>
        <CheckCircle2 className="h-4 w-4 text-success" />
      </div>
    );
  if (status === "failed")
    return (
      <div className={cn(base, "bg-destructive/10")}>
        <XCircle className="h-4 w-4 text-destructive" />
      </div>
    );
  return (
    <div className={cn(base, "bg-secondary")}>
      <AlertTriangle className="h-4 w-4 text-muted-foreground" />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: "bg-primary/10 text-primary",
    queued: "bg-secondary text-muted-foreground",
    done: "bg-success/10 text-success",
    failed: "bg-destructive/10 text-destructive",
    cancelled: "bg-secondary text-muted-foreground",
    interrupted: "bg-warning/10 text-warning",
  };
  return (
    <span
      className={cn(
        "rounded-md px-2 py-0.5 text-[10px] font-medium capitalize",
        styles[status] ?? styles.queued
      )}
    >
      {status}
    </span>
  );
}

function formatDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return `${m}m ${rem}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
