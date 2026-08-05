import { Check, X, AlertTriangle, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/api/types";

/*
 * Pipeline trace — a vertical run of steps joined by a rule.
 *
 * Chosen over a horizontal progress bar because the steps are not
 * interchangeable ticks: they have names, they fail for different reasons, and
 * one of them (synthesize) is allowed to be skipped without failing the job. A
 * vertical trace has room to say which step and why, and it reads like a log,
 * which is what a person watching a five-minute pipeline actually wants.
 */

const STEP_LABELS: Record<string, string> = {
  scrape: "Transcribe audio",
  ingest: "Parse & chunk",
  index: "Embed & index",
  extract_claims: "Extract claims",
  cluster: "Cluster claims",
  synthesize: "Cross-source synthesis",
  report: "Write brief",
};

const STEP_NOTES: Record<string, string> = {
  scrape: "Downloading audio and running speech-to-text — the slow part",
  ingest: "Splitting the transcript into retrievable passages",
  index: "Building vector and keyword indexes",
  extract_claims: "Pulling atomic claims, each tied to evidence",
  cluster: "Merging duplicates, separating distinct ideas",
  synthesize: "Comparing claims across sources for agreement and conflict",
  report: "Assembling the cited brief",
};

interface StepChecklistProps {
  steps: string[];
  currentStep: string | null;
  stepIndex: number;
  status: JobStatus;
  progress: number;
}

type StepState = "done" | "active" | "pending" | "failed" | "halted";

export function StepChecklist({
  steps,
  currentStep,
  stepIndex,
  status,
}: StepChecklistProps) {
  function stateOf(i: number): StepState {
    if (status === "done") return "done";
    if (i < stepIndex) return "done";
    if (i > stepIndex) return "pending";
    // i === stepIndex — the step in flight, or where it stopped
    if (status === "running") return "active";
    if (status === "failed") return "failed";
    if (status === "cancelled" || status === "interrupted") return "halted";
    return "pending"; // queued
  }

  return (
    <ol className="relative">
      {/* Connector rule behind the markers */}
      <span
        aria-hidden
        className="absolute left-[7px] top-3 bottom-3 w-px bg-border"
      />

      {steps.map((step, i) => {
        const state = stateOf(i);
        const isCurrent = state === "active" || state === "failed" || state === "halted";
        return (
          <li key={step} className="relative flex gap-4 pb-5 last:pb-0">
            <Marker state={state} />

            <div className="min-w-0 flex-1 -mt-0.5">
              <div className="flex items-baseline gap-2">
                <span
                  className={cn(
                    "text-[13px] leading-snug transition-colors",
                    state === "done" && "text-muted-foreground",
                    state === "active" && "font-medium text-foreground",
                    state === "pending" && "text-muted-foreground/45",
                    state === "failed" && "font-medium text-destructive",
                    state === "halted" && "font-medium text-primary"
                  )}
                >
                  {STEP_LABELS[step] ?? step}
                </span>
                <span className="tabular font-mono text-[10px] text-muted-foreground/40">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>

              {/* Only the live step explains itself — keeps the trace scannable */}
              {isCurrent && STEP_NOTES[step] && (
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  {STEP_NOTES[step]}
                </p>
              )}
            </div>

            {state === "active" && (
              <span className="mt-1 shrink-0">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                </span>
              </span>
            )}
          </li>
        );
      })}

      {/* Screen-reader summary — the visual trace is decorative for AT */}
      <span className="sr-only">
        {status === "done"
          ? "All steps complete."
          : currentStep
            ? `Step ${stepIndex + 1} of ${steps.length}: ${STEP_LABELS[currentStep] ?? currentStep}, ${status}.`
            : `Queued. ${steps.length} steps pending.`}
      </span>
    </ol>
  );
}

function Marker({ state }: { state: StepState }) {
  const base =
    "relative z-10 mt-0.5 flex h-[15px] w-[15px] shrink-0 items-center justify-center rounded-full border bg-background";

  if (state === "done")
    return (
      <span className={cn(base, "border-success/40 bg-success/15")}>
        <Check className="h-2.5 w-2.5 text-success" strokeWidth={3} />
      </span>
    );

  if (state === "active")
    return (
      <span className={cn(base, "border-primary")}>
        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      </span>
    );

  if (state === "failed")
    return (
      <span className={cn(base, "border-destructive/50 bg-destructive/15")}>
        <X className="h-2.5 w-2.5 text-destructive" strokeWidth={3} />
      </span>
    );

  if (state === "halted")
    return (
      <span className={cn(base, "border-primary/50 bg-primary/10")}>
        <AlertTriangle className="h-2.5 w-2.5 text-primary" strokeWidth={2.5} />
      </span>
    );

  return (
    <span className={cn(base, "border-border")}>
      <Minus className="h-2 w-2 text-muted-foreground/30" strokeWidth={3} />
    </span>
  );
}

/* ── CONDENSED VARIANT ──────────────────────────────────────────────────────
   Used in the batch view and job history, where a full trace per row would
   drown the list. Same state logic, reduced to a row of dashes. */

export function StepTrackMini({
  steps,
  stepIndex,
  status,
}: {
  steps: string[];
  stepIndex: number;
  status: JobStatus;
}) {
  return (
    <div className="flex items-center gap-[3px]" aria-hidden>
      {steps.map((s, i) => {
        const done = status === "done" || i < stepIndex;
        const active = i === stepIndex && status === "running";
        const bad = i === stepIndex && (status === "failed" || status === "cancelled" || status === "interrupted");
        return (
          <span
            key={s}
            className={cn(
              "h-[3px] w-3.5 rounded-full transition-colors",
              done && "bg-success/70",
              active && "animate-pulse bg-primary",
              bad && "bg-destructive/70",
              !done && !active && !bad && "bg-border"
            )}
          />
        );
      })}
    </div>
  );
}
