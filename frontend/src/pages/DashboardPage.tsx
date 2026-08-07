import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus,
  ArrowRight,
  FileText,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  FlaskConical,
} from "lucide-react";
import { useWorkspaces } from "@/hooks/useWorkspaces";
import { useJobs, useAddVideo } from "@/hooks/useJobs";
import { cn } from "@/lib/utils";

export function DashboardPage() {
  const navigate = useNavigate();
  const [quickUrl, setQuickUrl] = useState("");
  const [quickWs, setQuickWs] = useState("");

  const { data: workspacesData, isLoading: wsLoading } = useWorkspaces();
  const { data: jobsData, isLoading: jobsLoading } = useJobs();
  const addVideo = useAddVideo();

  const workspaces = workspacesData?.workspaces ?? [];
  const jobs = jobsData?.jobs ?? [];
  const activeJobs = jobs.filter(
    (j) => j.status === "running" || j.status === "queued"
  );

  // Aggregate stats
  const totalSources = workspaces.reduce((sum, w) => sum + w.videos, 0);
  const totalClaims = workspaces.reduce((sum, w) => sum + w.claims, 0);
  const totalReports = workspaces.filter((w) => w.has_report).length;

  function handleQuickSubmit(e: React.FormEvent) {
    e.preventDefault();
    const url = quickUrl.trim();
    const ws = quickWs.trim();
    if (!url) return toast.error("Paste a YouTube URL");
    if (!ws) return toast.error("Enter a workspace name");

    addVideo.mutate(
      { url, workspaceId: ws, engine: "cloud" },
      {
        onSuccess: (d) => navigate(`/processing/${d.job_id}`),
        onError: (err) => toast.error(err.message || "Could not queue the video"),
      }
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your evidence-backed video research at a glance.
          </p>
        </div>
        <Link
          to="/research/new"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Research
        </Link>
      </div>

      {/* Quick add */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-sm font-medium text-foreground">Quick add a source</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Paste a YouTube URL and it will be transcribed, indexed, and analyzed.
        </p>
        <form onSubmit={handleQuickSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="url"
            placeholder="https://www.youtube.com/watch?v=…"
            value={quickUrl}
            onChange={(e) => setQuickUrl(e.target.value)}
            className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <input
            type="text"
            placeholder="Workspace name"
            value={quickWs}
            onChange={(e) => setQuickWs(e.target.value)}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring sm:w-44"
          />
          <button
            type="submit"
            disabled={addVideo.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {addVideo.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="h-4 w-4" />
            )}
            Process
          </button>
        </form>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          icon={FileText}
          value={totalSources}
          label="Sources processed"
          loading={wsLoading}
        />
        <StatCard
          icon={CheckCircle2}
          value={totalClaims}
          label="Claims extracted"
          loading={wsLoading}
        />
        <StatCard
          icon={MessageSquare}
          value={totalReports}
          label="Reports generated"
          loading={wsLoading}
        />
        <StatCard
          icon={AlertTriangle}
          value={activeJobs.length}
          label="Active jobs"
          loading={jobsLoading}
          accent={activeJobs.length > 0}
        />
      </div>

      {/* Active jobs */}
      {activeJobs.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">Currently processing</h2>
            <Link
              to="/processing"
              className="text-xs text-primary hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="space-y-2">
            {activeJobs.slice(0, 3).map((job) => (
              <Link
                key={job.job_id}
                to={`/processing/${job.job_id}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/30"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {job.params.workspace_id}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {job.current_step ?? "Queued"} · {job.progress}%
                  </p>
                </div>
                <div className="h-2 w-24 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Recent workspaces */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-foreground">Recent research</h2>
          {workspaces.length > 0 && (
            <Link
              to="/research"
              className="text-xs text-primary hover:underline"
            >
              View all →
            </Link>
          )}
        </div>
        {wsLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-32 animate-pulse rounded-xl border border-border bg-card"
              />
            ))}
          </div>
        ) : workspaces.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-card p-12 text-center">
            <FlaskConical className="mx-auto h-8 w-8 text-muted-foreground/50" />
            <p className="mt-3 text-sm text-muted-foreground">
              No research yet. Add your first YouTube source to get started.
            </p>
            <Link
              to="/research/new"
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              Start research
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {workspaces.slice(0, 6).map((ws) => (
              <Link
                key={ws.id}
                to={`/research/${ws.id}`}
                className="group rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md"
              >
                <h3 className="truncate text-sm font-medium text-foreground group-hover:text-primary">
                  {ws.id}
                </h3>
                <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    {ws.videos} source{ws.videos !== 1 ? "s" : ""}
                  </span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    {ws.claims} claims
                  </span>
                </div>
                {ws.has_report && (
                  <span className="mt-3 inline-flex items-center gap-1 rounded-md bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">
                    <CheckCircle2 className="h-3 w-3" />
                    Report ready
                  </span>
                )}
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  value,
  label,
  loading,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: number;
  label: string;
  loading?: boolean;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <Icon
          className={cn(
            "h-4 w-4",
            accent ? "text-warning" : "text-muted-foreground"
          )}
        />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      {loading ? (
        <div className="mt-2 h-7 w-12 animate-pulse rounded bg-secondary" />
      ) : (
        <p className={cn("mt-2 text-2xl font-semibold tabular", accent ? "text-warning" : "text-foreground")}>
          {value}
        </p>
      )}
    </div>
  );
}
