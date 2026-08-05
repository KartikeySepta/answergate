import { useEffect, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { MicroLabel } from "@/components/ui/primitives";

/*
 * Raw pipeline output, collapsed by default.
 *
 * The backend's steps already print useful detail (chunk counts, cache hits,
 * how many Gemini calls a run cost) and that is exactly what you want when a
 * job looks stuck or a claim count seems wrong. Kept collapsed so the trace
 * stays the focus, and auto-scrolled while open so it behaves like a tail.
 */

export function JobLogPanel({
  log,
  defaultOpen = false,
}: {
  log: string[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log.length, open]);

  if (!log.length) return null;

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-accent/40"
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90"
          )}
        />
        <MicroLabel>pipeline output</MicroLabel>
        <span className="tabular ml-auto font-mono text-[10px] text-muted-foreground/60">
          {log.length} lines
        </span>
      </button>

      {open && (
        <div
          ref={scrollRef}
          className="max-h-64 overflow-y-auto border-t border-border bg-background/60 px-3 py-2.5"
        >
          <pre className="font-mono text-[11px] leading-[1.7] text-muted-foreground">
            {log.map((line, i) => (
              <div key={i} className="flex gap-3">
                <span className="tabular w-6 shrink-0 select-none text-right text-muted-foreground/30">
                  {i + 1}
                </span>
                <span
                  className={cn(
                    "min-w-0 whitespace-pre-wrap break-words",
                    /error|failed|traceback/i.test(line) && "text-destructive",
                    /warning|skipped/i.test(line) && "text-primary/90"
                  )}
                >
                  {line}
                </span>
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
