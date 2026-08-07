import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowRight,
  Cloud,
  HardDrive,
  Link2,
  List,
  Loader2,
  Video,
} from "lucide-react";
import { useAddVideo, useAddBatch } from "@/hooks/useJobs";
import { useWorkspaces } from "@/hooks/useWorkspaces";
import { cn } from "@/lib/utils";

type Mode = "single" | "batch";
type Engine = "cloud" | "local";

export function NewResearchPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("single");
  const [engine, setEngine] = useState<Engine>("cloud");
  const [url, setUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");

  const { data: workspacesData } = useWorkspaces();
  const addVideo = useAddVideo();
  const addBatch = useAddBatch();
  const isPending = addVideo.isPending || addBatch.isPending;

  const workspaces = workspacesData?.workspaces ?? [];
  const urlCount = batchUrls.split("\n").filter((u) => u.trim()).length;
  const existing = workspaces.find((w) => w.id === workspaceId.trim());

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ws = workspaceId.trim();
    if (!ws) return toast.error("Enter a workspace name");

    if (mode === "single") {
      const u = url.trim();
      if (!u) return toast.error("Paste a YouTube URL");
      addVideo.mutate(
        { url: u, workspaceId: ws, engine },
        {
          onSuccess: (d) => navigate(`/processing/${d.job_id}`),
          onError: (err) => toast.error(err.message || "Could not queue the video"),
        }
      );
    } else {
      const urls = batchUrls
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean);
      if (!urls.length) return toast.error("Add at least one URL");
      addBatch.mutate(
        { urls, workspaceId: ws, engine },
        {
          onSuccess: () => navigate("/processing"),
          onError: (err) => toast.error(err.message || "Could not queue the batch"),
        }
      );
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          New Research
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Add YouTube sources to create or extend a research workspace. Each video
          is transcribed, indexed, and analyzed for claims.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Mode toggle */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <label className="text-sm font-medium text-foreground">Source type</label>
          <div className="mt-3 flex gap-2">
            <ModeButton
              active={mode === "single"}
              onClick={() => setMode("single")}
              icon={Link2}
              label="Single URL"
            />
            <ModeButton
              active={mode === "batch"}
              onClick={() => setMode("batch")}
              icon={List}
              label="Multiple URLs"
            />
          </div>

          {/* URL input */}
          <div className="mt-4">
            {mode === "single" ? (
              <div>
                <input
                  type="url"
                  autoFocus
                  placeholder="https://www.youtube.com/watch?v=…"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2.5 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  Supports youtube.com/watch, youtu.be, and /shorts links.
                </p>
              </div>
            ) : (
              <div>
                <textarea
                  autoFocus
                  rows={5}
                  placeholder={"https://www.youtube.com/watch?v=…\nhttps://youtu.be/…\nhttps://www.youtube.com/watch?v=…"}
                  value={batchUrls}
                  onChange={(e) => setBatchUrls(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2.5 font-mono text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  One URL per line, up to 50. Each becomes its own processing job.
                  {urlCount > 0 && (
                    <span className="ml-1 font-medium text-foreground">
                      {urlCount} URL{urlCount !== 1 ? "s" : ""} queued.
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Workspace */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <label htmlFor="ws" className="text-sm font-medium text-foreground">
            Research workspace
          </label>
          <p className="mt-1 text-xs text-muted-foreground">
            Create a new workspace or add to an existing one for cross-video analysis.
          </p>
          <input
            id="ws"
            type="text"
            list="ws-suggestions"
            placeholder="e.g. ai-agents-2024"
            value={workspaceId}
            onChange={(e) => setWorkspaceId(e.target.value)}
            className="mt-3 w-full rounded-lg border border-input bg-background px-3 py-2.5 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <datalist id="ws-suggestions">
            {workspaces.map((w) => (
              <option key={w.id} value={w.id} />
            ))}
          </datalist>

          {/* Existing workspace hint */}
          {existing && (
            <div className="mt-3 flex items-center gap-2 rounded-lg bg-primary/5 px-3 py-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              <p className="text-xs text-muted-foreground">
                Adding to <span className="font-medium text-foreground">{existing.id}</span> ·{" "}
                {existing.videos} source{existing.videos !== 1 ? "s" : ""}, {existing.claims} claims.
                New material will be compared with existing sources.
              </p>
            </div>
          )}

          {/* Quick workspace chips */}
          {workspaces.length > 0 && !workspaceId && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {workspaces.slice(0, 8).map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => setWorkspaceId(w.id)}
                  className="rounded-md border border-border px-2.5 py-1 font-mono text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {w.id}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Engine selection */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <label className="text-sm font-medium text-foreground">
            Transcription engine
          </label>
          <div className="mt-3 flex gap-2">
            <ModeButton
              active={engine === "cloud"}
              onClick={() => setEngine("cloud")}
              icon={Cloud}
              label="Cloud (Gemini)"
              description="Fast and accurate"
            />
            <ModeButton
              active={engine === "local"}
              onClick={() => setEngine("local")}
              icon={HardDrive}
              label="Local (Whisper)"
              description="No API cost, handles long videos"
            />
          </div>
        </div>

        {/* Pipeline preview */}
        <div className="rounded-xl border border-dashed border-border bg-secondary/30 p-4">
          <p className="text-xs font-medium text-muted-foreground">Pipeline steps</p>
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            {[
              "Download",
              "Transcribe",
              "Chunk & Index",
              "Extract Claims",
              "Cluster",
              "Synthesize",
              "Generate Report",
            ].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-1">
                <span className="rounded bg-secondary px-1.5 py-0.5">{step}</span>
                {i < arr.length - 1 && (
                  <ArrowRight className="h-3 w-3 text-muted-foreground/40" />
                )}
              </span>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="rounded-lg px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Queueing…
              </>
            ) : (
              <>
                <Video className="h-4 w-4" />
                {mode === "single"
                  ? "Start research"
                  : `Process ${urlCount || ""} sources`.trim()}
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  icon: Icon,
  label,
  description,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center gap-3 rounded-lg border px-4 py-3 text-left transition-all",
        active
          ? "border-primary bg-primary/5 text-foreground"
          : "border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground"
      )}
    >
      <Icon className={cn("h-4 w-4", active ? "text-primary" : "")} />
      <div>
        <p className="text-sm font-medium">{label}</p>
        {description && <p className="text-[11px] text-muted-foreground">{description}</p>}
      </div>
    </button>
  );
}
