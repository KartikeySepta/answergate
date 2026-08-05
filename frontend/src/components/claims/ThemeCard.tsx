import type { Theme } from "@/api/types";
import { MicroLabel, Mono } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

/*
 * A cross-source theme is a relationship between two videos, so the
 * relationship is the headline and the note explains it. Agreement and
 * contradiction get colour because those are the two findings a researcher is
 * actually hunting for; the rest stay neutral.
 */

const REL: Record<Theme["relationship"], { label: string; tone: string; dot: string }> = {
  agreement: { label: "agree", tone: "text-success", dot: "bg-success" },
  contradiction: { label: "conflict", tone: "text-destructive", dot: "bg-destructive" },
  partial_agreement: { label: "partial", tone: "text-primary", dot: "bg-primary" },
  different_context: {
    label: "different scope",
    tone: "text-muted-foreground",
    dot: "bg-muted-foreground/50",
  },
  independent: {
    label: "independent",
    tone: "text-muted-foreground",
    dot: "bg-muted-foreground/40",
  },
  related: { label: "related", tone: "text-muted-foreground", dot: "bg-muted-foreground/50" },
};

export function ThemeCard({ theme }: { theme: Theme }) {
  const r = REL[theme.relationship] ?? REL.related;

  return (
    <div className="py-4">
      <div className="mb-2 flex items-center gap-2.5">
        <span className={cn("h-1 w-1 shrink-0 rounded-full", r.dot)} />
        <MicroLabel className={r.tone}>{r.label}</MicroLabel>
        <span className="tabular ml-auto font-mono text-[10px] text-muted-foreground/45">
          {theme.cosine.toFixed(2)}
        </span>
      </div>

      <p className="text-[13.5px] leading-relaxed text-foreground">
        {theme.synthesis_note}
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        <MicroLabel className="text-muted-foreground/50">across</MicroLabel>
        {theme.videos.map((v) => (
          <Mono key={v} dim>
            {v}
          </Mono>
        ))}
      </div>
    </div>
  );
}
