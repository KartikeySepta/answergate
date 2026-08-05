import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Cloud, HardDrive, Link2, List, ArrowRight } from "lucide-react";
import { useAddVideo, useAddBatch } from "@/hooks/useJobs";
import { useWorkspaces } from "@/hooks/useWorkspaces";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Field,
  MicroLabel,
  PageHeader,
  Segmented,
  Mono,
} from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

type Mode = "single" | "batch";
type Engine = "cloud" | "local";

export function AddVideoPage() {
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
    if (!ws) return toast.error("Name a workspace to collect this research into");

    if (mode === "single") {
      const u = url.trim();
      if (!u) return toast.error("Paste a YouTube URL");
      addVideo.mutate(
        { url: u, workspaceId: ws, engine },
        {
          onSuccess: (d) => navigate(`/jobs/${d.job_id}`),
          onError: (err) => toast.error(err.message || "Could not queue the video"),
        }
      );
      return;
    }

    const urls = batchUrls.split("\n").map((u) => u.trim()).filter(Boolean);
    if (!urls.length) return toast.error("Add at least one URL");
    addBatch.mutate(
      { urls, workspaceId: ws, engine },
      {
        onSuccess: () => navigate("/jobs"),
        onError: (err) => toast.error(err.message || "Could not queue the batch"),
      }
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="step 01"
        title="Add a source"
        description="Paste a YouTube URL. It gets transcribed, chunked, and mined for claims — every one traceable back to a timestamp."
      />

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Source input — the primary action, so it leads */}
        <Field
          label={mode === "single" ? "Source URL" : `Source URLs · ${urlCount} queued`}
          htmlFor="src"
          hint={
            mode === "single"
              ? "youtube.com/watch, youtu.be, and /shorts links all work."
              : "One URL per line, up to 50. Each becomes its own job so you can watch them individually."
          }
        >
          <div className="space-y-2">
            <Segmented
              size="sm"
              value={mode}
              onChange={setMode}
              options={[
                { value: "single", label: "One", icon: Link2 },
                { value: "batch", label: "Many", icon: List },
              ]}
            />
            {mode === "single" ? (
              <Input
                id="src"
                type="url"
                autoFocus
                spellCheck={false}
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="font-mono text-[13px]"
              />
            ) : (
              <Textarea
                id="src"
                autoFocus
                spellCheck={false}
                rows={6}
                placeholder={"https://www.youtube.com/watch?v=…\nhttps://youtu.be/…"}
                value={batchUrls}
                onChange={(e) => setBatchUrls(e.target.value)}
                className="font-mono text-[13px] leading-relaxed"
              />
            )}
          </div>
        </Field>

        {/* Workspace */}
        <Field
          label="Collect into"
          htmlFor="ws"
          hint={
            existing
              ? undefined
              : "New workspaces are created on the fly. Letters, numbers, dash, underscore."
          }
        >
          <Input
            id="ws"
            list="ws-options"
            spellCheck={false}
            placeholder="e.g. ai-agents"
            value={workspaceId}
            onChange={(e) => setWorkspaceId(e.target.value)}
            className="font-mono text-[13px]"
          />
          <datalist id="ws-options">
            {workspaces.map((w) => (
              <option key={w.id} value={w.id} />
            ))}
          </datalist>

          {/* Adding to an existing workspace is a meaningfully different act —
              it makes cross-video synthesis possible — so say so. */}
          {existing && (
            <p className="flex items-center gap-2 text-[12px] text-muted-foreground">
              <span className="h-1 w-1 rounded-full bg-primary" />
              Joining <Mono>{existing.id}</Mono> · {existing.videos} source
              {existing.videos === 1 ? "" : "s"}, {existing.claims} claims. New
              material will be compared against what's already there.
            </p>
          )}

          {workspaces.length > 0 && !workspaceId && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {workspaces.slice(0, 6).map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => setWorkspaceId(w.id)}
                  className="rounded border border-border px-2 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {w.id}
                </button>
              ))}
            </div>
          )}
        </Field>

        {/* Engine */}
        <Field
          label="Transcription"
          hint={
            engine === "cloud"
              ? "Gemini. Fast and accurate, but long videos can truncate past ~90 minutes."
              : "Whisper on this machine. Slower, no API cost, and handles multi-hour videos without truncating."
          }
        >
          <Segmented
            value={engine}
            onChange={setEngine}
            options={[
              { value: "cloud", label: "Cloud", icon: Cloud },
              { value: "local", label: "Local", icon: HardDrive },
            ]}
          />
        </Field>

        <hr className="border-border" />

        {/* Submit + what happens next, stated plainly rather than hidden */}
        <div className="flex items-center justify-between gap-4">
          <div className="hidden sm:block">
            <MicroLabel className="block">then</MicroLabel>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">
              transcribe → chunk → index → claims → cluster → synthesize → brief
            </p>
          </div>
          <button
            type="submit"
            disabled={isPending}
            className={cn(
              "group inline-flex shrink-0 items-center gap-2 rounded-md bg-primary px-4 py-2.5",
              "text-[13px] font-medium text-primary-foreground transition-opacity",
              "hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            )}
          >
            {isPending
              ? "Queueing…"
              : mode === "single"
                ? "Process source"
                : `Process ${urlCount || ""} sources`.trim()}
            {!isPending && (
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
