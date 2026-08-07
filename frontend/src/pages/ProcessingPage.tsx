import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
  Ban,
  ExternalLink,
} from "lucide-react";
import { useJobPolling } from "@/hooks/useJobPolling";
import { useCancelJob } from "@/hooks/useJobs";
import { cn } from "@/lib/utils";

const STEP_LABELS: Record<string, string> = {
  scrape: "Downloading & Transcribing",
  ingest: "Parsing transcript",
  index: "Building search index",
  extract_claims: "Extracting claims",
  cluster: "Clustering related claims",
  synthesize: "Cross-source synthesis",
  report: "Writing research brief",
};

export function ProcessingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [showLogs, setShowLogs] = useState(false);

  const { job, isLoading, isStale, error } = useJobPolling(jobId ?? null);
  const cancelJob = useCancelJob();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="mx-auto max-w-lg text-center py-20">
        <XCircle className="mx-auto h-10 w-10 text-destructive/60" />
        <h2 className="mt-4 text-lg font-medium text-foreground">Job not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {error?.message ?? "This job may have been removed or doesn't exist."}
        </p>
        <Link
          to="/processing"
          className="mt-6 inline-flex items-center gap-2 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to processing centre
        </Link>
      </div>
    );
  }

  const isDone = job.status === "done";
  const isFailed = job.status === "failed";
  const isRunning = job.status === "running" || job.status === "queued";

  const elapsed = job.duration_seconds
    ? formatDuration(job.duration_seconds)
    : job.started_at
      ? formatDuration(Date.now() / 1000 - job.started_at)
      : null;

  return (
    <div className="mx-auto max-w-2xl">
      {/* Back */}
      <Link
        to="/processing"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All jobs
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <StatusIcon status={job.status} />
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              {job.params.workspace_id}
            </h1>
            <p className="mt-0.5 text-xs font-mono text-muted-foreground truncate max-w-md">
              {job.params.url}
            </p>
          </div>
        </div>

        {/* Meta row */}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <StatusBadge status={job.status} />
          {elapsed && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {elapsed}
            </span>
          )}
          {job.params.engine && (
            <span className="rounded-md bg-secondary px-2 py-0.5">
              {job.params.engine}
            </span>
          )}
          {isStale && (
            <span className="text-warning">Connection lost · showing last known state</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {isRunning && (
        <div className="mb-8">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {job.current_step ? STEP_LABELS[job.current_step] ?? job.current_step : "Queued"}
            </span>
            <span className="tabular font-medium text-foreground">{job.progress}%</span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Pipeline steps */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-medium text-foreground">Pipeline</h2>
        <div className="space-y-3">
          {job.steps.map((step, i) => {
            const state = getStepState(i, job.step_index, job.status);
            return (
              <div key={step} className="flex items-center gap-3">
                <StepIndicator state={state} />
                <span
                  className={cn(
                    "text-sm",
                    state === "active"
                      ? "font-medium text-foreground"
                      : state === "done"
                        ? "text-muted-foreground"
                        : "text-muted-foreground/60"
                  )}
                >
                  {STEP_LABELS[step] ?? step}
                </span>
                {state === "active" && isRunning && (
                  <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-primary" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Done state */}
      {isDone && job.result && (
        <div className="mt-6 rounded-xl border border-success/30 bg-success/5 p-6">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-success" />
            <h2 className="text-sm font-medium text-foreground">Research complete</h2>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-muted-foreground">Sources</p>
              <p className="font-medium text-foreground">{job.result.videos}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Chunks</p>
              <p className="font-medium text-foreground">{job.result.chunks}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Claims</p>
              <p className="font-medium text-foreground">{job.result.claims}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Report</p>
              <p className="font-medium text-foreground">{job.result.has_report ? "Ready" : "—"}</p>
            </div>
          </div>
          <Link
            to={`/research/${job.params.workspace_id}`}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Open workspace
          </Link>
        </div>
      )}

      {/* Failed state */}
      {isFailed && (
        <div className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-6">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-destructive" />
            <h2 className="text-sm font-medium text-foreground">Processing failed</h2>
          </div>
          {job.error && (
            <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-secondary p-3 font-mono text-xs text-destructive">
              {job.error}
            </pre>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 flex items-center gap-3">
        {isRunning && (
          <button
            onClick={() =>
              cancelJob.mutate(job.job_id, {
                onSuccess: () => toast.success("Job cancelled"),
                onError: (e) => toast.error(e.message),
              })
            }
            disabled={cancelJob.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-destructive/30 px-4 py-2 text-sm text-destructive transition-colors hover:bg-destructive/5 disabled:opacity-50"
          >
            <Ban className="h-3.5 w-3.5" />
            Cancel
          </button>
        )}

        {/* Logs toggle */}
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          {showLogs ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {showLogs ? "Hide logs" : "Show logs"}
        </button>
      </div>

      {/* Logs */}
      {showLogs && job.log && (
        <div className="mt-4 max-h-64 overflow-auto rounded-xl border border-border bg-card p-4">
          <pre className="font-mono text-xs leading-relaxed text-muted-foreground">
            {job.log.length > 0 ? job.log.join("\n") : "No output yet…"}
          </pre>
        </div>
      )}
    </div>
  );
}

// --- Helpers ---

function getStepState(
  stepIndex: number,
  currentIndex: number,
  status: string
): "done" | "active" | "pending" | "failed" {
  if (status === "failed" && stepIndex === currentIndex) return "failed";
  if (stepIndex < currentIndex) return "done";
  if (stepIndex === currentIndex && (status === "running" || status === "done")) return status === "done" ? "done" : "active";
  return "pending";
}

function StepIndicator({ state }: { state: "done" | "active" | "pending" | "failed" }) {
  if (state === "done") {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-success/10">
        <CheckCircle2 className="h-3.5 w-3.5 text-success" />
      </div>
    );
  }
  if (state === "active") {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10">
        <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
      </div>
    );
  }
  if (state === "failed") {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-destructive/10">
        <XCircle className="h-3.5 w-3.5 text-destructive" />
      </div>
    );
  }
  return (
    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-secondary">
      <div className="h-2 w-2 rounded-full bg-muted-foreground/30" />
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "done") return <CheckCircle2 className="h-8 w-8 text-success" />;
  if (status === "failed") return <XCircle className="h-8 w-8 text-destructive" />;
  if (status === "cancelled" || status === "interrupted")
    return <Ban className="h-8 w-8 text-muted-foreground" />;
  return <Loader2 className="h-8 w-8 animate-spin text-primary" />;
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
    <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium capitalize", styles[status] ?? styles.queued)}>
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
