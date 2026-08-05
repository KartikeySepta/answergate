import { useState } from "react";
import { cn } from "@/lib/utils";

/*
 * An inline citation, styled like a highlighter mark on the number itself.
 *
 * Focusable and toggled by click or Enter/Space rather than hover-only: this is
 * a research tool, and checking a source is a deliberate act people will do
 * with the keyboard while reading. Hover-only tooltips also vanish on touch.
 */

export function CitationChip({
  label,
  videoTitle,
  timestamp,
}: {
  label: string;
  videoTitle: string;
  timestamp: string;
}) {
  const [open, setOpen] = useState(false);
  const n = label.replace(/\D/g, "") || label;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-expanded={open}
        aria-label={`${label}: ${videoTitle} at ${timestamp}`}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "mx-[1px] inline-flex items-baseline rounded-[3px] px-1 align-baseline",
          "tabular font-mono text-[10px] transition-colors",
          open
            ? "bg-primary text-primary-foreground"
            : "bg-primary/15 text-primary hover:bg-primary/25"
        )}
      >
        {n}
      </button>

      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-20 mt-1.5 block w-64 rounded-md border border-border bg-popover p-2.5 shadow-lg"
        >
          <span className="block font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
            {label} · {timestamp}
          </span>
          <span className="mt-1 block text-[12px] leading-snug text-foreground">
            {videoTitle}
          </span>
        </span>
      )}
    </span>
  );
}
