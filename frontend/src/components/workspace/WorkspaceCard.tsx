import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { Workspace } from "@/api/types";
import { MicroLabel } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

/*
 * A workspace as a catalogue entry: index number, name in mono (it IS an
 * identifier, you type it into the CLI), then counts as small tabular facts.
 * The "brief" marker is the only coloured thing, because having a readable
 * brief is the one status difference that changes what you do next.
 */

export function WorkspaceCard({ workspace, n }: { workspace: Workspace; n: number }) {
  const { id, videos, claims, has_report } = workspace;

  return (
    <Link
      to={`/workspaces/${id}`}
      className={cn(
        "group relative flex flex-col justify-between gap-6 rounded-md border border-border bg-card/50 p-4",
        "transition-colors hover:border-primary/30 hover:bg-card"
      )}
    >
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="tabular font-mono text-[10px] text-muted-foreground/40">
            {String(n).padStart(2, "0")}
          </span>
          <ArrowUpRight className="h-3 w-3 text-muted-foreground/0 transition-colors group-hover:text-muted-foreground" />
        </div>
        <h3 className="truncate font-mono text-[14px] text-foreground">{id}</h3>
      </div>

      <div className="flex items-end justify-between">
        <div className="flex gap-5">
          <div>
            <div className="tabular font-mono text-[15px] leading-none text-foreground">
              {videos}
            </div>
            <MicroLabel className="mt-1 block">
              {videos === 1 ? "source" : "sources"}
            </MicroLabel>
          </div>
          <div>
            <div className="tabular font-mono text-[15px] leading-none text-foreground">
              {claims}
            </div>
            <MicroLabel className="mt-1 block">claims</MicroLabel>
          </div>
        </div>

        {has_report && (
          <span className="flex items-center gap-1.5">
            <span className="h-1 w-1 rounded-full bg-primary" />
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-primary">
              brief
            </span>
          </span>
        )}
      </div>
    </Link>
  );
}
