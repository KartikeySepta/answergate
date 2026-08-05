import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Claim } from "@/api/types";
import { MicroLabel, Mono } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

/*
 * A claim with its evidence folded underneath.
 *
 * The claim text is the only sans-serif thing at full size; type, stance and
 * ids are all mono metadata. Evidence opens into a highlighter-washed block —
 * literally the marked-up passage the claim came from, which is the entire
 * point of the product.
 */

const TYPE_TONE: Record<Claim["claim_type"], string> = {
  fact: "text-foreground/70",
  recommendation: "text-primary/90",
  opinion: "text-muted-foreground",
  warning: "text-destructive/90",
  prediction: "text-muted-foreground",
};

const STANCE_DOT: Record<Claim["stance"], string> = {
  support: "bg-success",
  oppose: "bg-destructive",
  neutral: "bg-muted-foreground/40",
  mixed: "bg-primary",
};

export function ClaimCard({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const evidenceCount = claim.evidence.length;

  return (
    <div className="py-4">
      {/* Metadata line */}
      <div className="mb-2 flex items-center gap-2.5">
        <span className={cn("h-1 w-1 shrink-0 rounded-full", STANCE_DOT[claim.stance])} />
        <MicroLabel className={TYPE_TONE[claim.claim_type]}>
          {claim.claim_type}
        </MicroLabel>
        <MicroLabel className="text-muted-foreground/50">{claim.stance}</MicroLabel>
        {claim.cluster_id && (
          <span
            className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground/40"
            title="Grouped with similar claims"
          >
            clustered
          </span>
        )}
      </div>

      {/* The claim */}
      <p className="text-[13.5px] leading-relaxed text-foreground">{claim.claim}</p>

      {/* Topics */}
      {claim.topics.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
          {claim.topics.map((t) => (
            <Mono key={t} dim>
              #{t}
            </Mono>
          ))}
        </div>
      )}

      {/* Evidence */}
      {evidenceCount > 0 && (
        <div className="mt-3">
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="group inline-flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronRight
              className={cn("h-3 w-3 transition-transform", open && "rotate-90")}
            />
            <MicroLabel className="group-hover:text-foreground">
              {evidenceCount} passage{evidenceCount === 1 ? "" : "s"}
            </MicroLabel>
          </button>

          {open && (
            <div className="mt-2.5 space-y-2.5">
              {claim.evidence.map((ev, i) => (
                <blockquote
                  key={ev.chunk_id + i}
                  className="border-l-2 border-l-primary/40 bg-primary/[0.04] py-2 pl-3 pr-2"
                >
                  <p className="text-[12.5px] leading-relaxed text-foreground/85">
                    {ev.evidence_text}
                  </p>
                  <Mono dim className="mt-1.5 block">
                    {ev.chunk_id}
                  </Mono>
                </blockquote>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
