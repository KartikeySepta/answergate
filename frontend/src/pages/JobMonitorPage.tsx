import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, RotateCw, WifiOff, X } from "lucide-react";
import { useJobPolling } from "@/hooks/useJobPolling";
import { useCancelJob, useAddVideo } from "@/hooks/useJobs";
import { StepChecklist } from "@/components/job/StepChecklist";
import { JobLogPanel } from "@/components/job/JobLogPanel";
import { JobStatusBadge } from "@/components/job/JobStatusBadge";
import {
  MicroLabel,
  Mono,
  PageHeader,
  Section,
  Stat,
} from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const REDIRECT_DELAY_MS = 1800;

export function JobMonitorPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { job, isLoading, isStale, error, refetch } = useJobPolling(jobId ?? null);
  const cancelJob = useCancelJob();
  const retry = useAddVideo();

  // Elapsed ticks locally so a running job never looks frozen between polls.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (job?.status !== "running") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [job?.status]);

  // On success, move the user to the thing they actually wanted: the research.
  useEffect(() => {
    if (job?.status !== "done") return;
    const ws = job.result?.workspace_id ?? job.params.workspace_id;
    const t = setTimeout(() => navigate(`/workspaces/${ws}`), REDIRECT_DELAY_MS);
    return () => clearTimeout(t);
  }, [job?.status, job?.result?.workspace_id, job?.params.workspace_id, navigate]);

  if (isLoading && !job) {
    return (
      <div>
        <PageHeader eyebrow="step 02" title="Processing" />
        <div className="space-y-4">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="flex gap-4">
              <div className="h-[15px] w-[15px] shrink-0 animate-pulse rounded-full bg-muted" />
              <div className="h-3 w-40 animate-pulse rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div>
        <PageHeader eyebrow="step 02" title="Job not found" />
        <p className="text-[13px] text-muted-foreground">
          No job with id <Mono>{jobId}</Mono>. It may have aged out of history.
        </p>
        <Link
          to="/jobs"
          className="mt-4 inline-flex items-center gap-1.5 text-[13px] text-primary hover:underline"
        >
          All jobs <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    );
  }

  if (!job) return null;

  const isLive = job.status === "running" || job.status === "queued";
  const elapsed = job.started_at
    ? (job.finished_at ?? now / 1000) - job.started_at
    : 0;

  return (
    <div>
      <PageHeader
        eyebrow={`step 02 · ${job.params.engine}`}
        title={job.params.workspace_id}
        description={job.params.url}
        actions={
          isLive ? (
            <button
              type="button"
              disabled={cancelJob.isPending}
              onClick={() =>
                cancelJob.mutate(job.job_id, {
                  onSuccess: () => toast.success("Cancelling after the current step"),
                  onError: (e) => toast.error(e.message),
                })
              }
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50"
            >
              <X className="h-3 w-3" />
              Cancel
            </button>
          ) : undefined
        }
      />

      {/* Connection lost — surfaced rather than retried forever */}
      {isStale && (
        <Callout tone="warn" icon={WifiOff} className="mb-6">
          <span>Lost contact with the server. Progress may have moved on.</span>
          <button
            onClick={() => refetch()}
            className="ml-2 font-medium text-primary hover:underline"
          >
            Retry now
          </button>
        </Callout>
      )}

      {/* Status strip */}
      <div className="mb-8 flex flex-wrap items-end justify-between gap-6 border-b border-border pb-6">
        <div className="flex items-end gap-8">
          <div>
            <MicroLabel className="mb-1.5 block">status</MicroLabel>
            <JobStatusBadge status={job.status} />
          </div>
          <Stat
            value={`${job.step_index}/${job.steps.length}`}
            label="steps"
          />
          <Stat value={formatElapsed(elapsed)} label="elapsed" accent={isLive} />
        </div>
        <Mono dim>{job.job_id}</Mono>
      </div>

      {/* The trace */}
      <div aria-live="polite" aria-atomic="false">
        <Section label="pipeline" className="mb-8">
          <StepChecklist
            steps={job.steps}
            currentStep={job.current_step}
            stepIndex={job.step_index}
            status={job.status}
            progress={job.progress}
          />
        </Section>
      </div>

      {/* Terminal states — each says something different and useful */}
      {job.status === "done" && job.result && (
        <Callout tone="ok" className="mb-6">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
            <span className="font-medium text-foreground">Brief ready.</span>
            <Mono dim>{job.result.videos} sources</Mono>
            <Mono dim>{job.result.chunks} passages</Mono>
            <Mono dim>{job.result.claims} claims</Mono>
          </div>
          <Link
            to={`/workspaces/${job.result.workspace_id}`}
            className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-medium text-primary hover:underline"
          >
            Open research <ArrowRight className="h-3 w-3" />
          </Link>
        </Callout>
      )}

      {job.status === "interrupted" && (
        <Callout tone="warn" className="mb-6">
          <p className="text-foreground">
            This job stopped when the server restarted — it was not a failure of
            the video.
          </p>
          <button
            disabled={retry.isPending}
            onClick={() =>
              retry.mutate(
                {
                  url: job.params.url,
                  workspaceId: job.params.workspace_id,
                  engine: job.params.engine as "cloud" | "local",
                },
                {
                  onSuccess: (d) => navigate(`/jobs/${d.job_id}`),
                  onError: (e) => toast.error(e.message),
                }
              )
            }
            className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-medium text-primary hover:underline disabled:opacity-50"
          >
            <RotateCw className="h-3 w-3" />
            {retry.isPending ? "Requeueing…" : "Run it again"}
          </button>
        </Callout>
      )}

      {job.status === "failed" && job.error && (
        <Callout tone="bad" className="mb-6">
          <MicroLabel className="mb-1.5 block">failure</MicroLabel>
          <p className="font-mono text-[12px] leading-relaxed text-destructive">
            {job.error}
          </p>
          <p className="mt-2 text-[12px] text-muted-foreground">
            The output below usually says which step and why.
          </p>
        </Callout>
      )}

      {job.status === "cancelled" && (
        <Callout tone="neutral" className="mb-6">
          Cancelled. Anything already indexed stayed in the workspace.
        </Callout>
      )}

      <JobLogPanel log={job.log} defaultOpen={job.status === "failed"} />
    </div>
  );
}

/* Callout: a left-ruled note rather than a filled alert box — same reason the
   status badges are dots, keeps the page calm while still being findable. */
function Callout({
  tone,
  icon: Icon,
  children,
  className,
}: {
  tone: "ok" | "warn" | "bad" | "neutral";
  icon?: React.ElementType;
  children: React.ReactNode;
  className?: string;
}) {
  const rule = {
    ok: "border-l-success",
    warn: "border-l-primary",
    bad: "border-l-destructive",
    neutral: "border-l-border",
  }[tone];

  return (
    <div
      className={cn(
        "border-l-2 bg-card/40 py-3 pl-4 pr-3 text-[13px] leading-relaxed text-muted-foreground",
        rule,
        className
      )}
    >
      {Icon ? (
        <div className="flex items-start gap-2">
          <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
          <div className="min-w-0">{children}</div>
        </div>
      ) : (
        children
      )}
    </div>
  );
}

function formatElapsed(seconds: number): string {
  if (!seconds || seconds < 0) return "0:00";
  const s = Math.floor(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}
