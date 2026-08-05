import type { Workspace } from "@/api/types";
import { WorkspaceCard } from "./WorkspaceCard";

export function WorkspaceGrid({ workspaces }: { workspaces: Workspace[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {workspaces.map((w, i) => (
        <WorkspaceCard key={w.id} workspace={w} n={i + 1} />
      ))}
    </div>
  );
}
