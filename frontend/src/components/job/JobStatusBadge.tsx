import { cn } from "@/lib/utils";
import type { JobStatus } from "@/api/types";

/*
 * Status is carried by a coloured dot plus a mono word, not a filled pill.
 * Pills read as buttons; these are read-only facts, and a list of ten of them
 * should stay quiet enough that the workspace names remain the thing you scan.
 */

const STYLES: Record<JobStatus, { dot: string; text: string; label: string }> = {
  queued: { dot: "bg-muted-foreground/50", text: "text-muted-foreground", label: "queued" },
  running: { dot: "bg-primary animate-pulse", text: "text-primary", label: "running" },
  done: { dot: "bg-success", text: "text-success", label: "done" },
  failed: { dot: "bg-destructive", text: "text-destructive", label: "failed" },
  interrupted: { dot: "bg-primary/70", text: "text-primary/90", label: "interrupted" },
  cancelled: { dot: "bg-muted-foreground/40", text: "text-muted-foreground/70", label: "cancelled" },
};

export function JobStatusBadge({
  status,
  className,
}: {
  status: JobStatus;
  className?: string;
}) {
  const s = STYLES[status] ?? STYLES.queued;
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", s.dot)} />
      <span
        className={cn(
          "font-mono text-[10px] uppercase tracking-[0.12em]",
          s.text
        )}
      >
        {s.label}
      </span>
    </span>
  );
}
