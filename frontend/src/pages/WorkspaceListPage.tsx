import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { useWorkspaces } from "@/hooks/useWorkspaces";
import { WorkspaceGrid } from "@/components/workspace/WorkspaceGrid";
import { EmptyState, PageHeader } from "@/components/ui/primitives";

export function WorkspaceListPage() {
  const { data, isLoading } = useWorkspaces();
  const workspaces = data?.workspaces ?? [];

  const totals = workspaces.reduce(
    (acc, w) => ({ videos: acc.videos + w.videos, claims: acc.claims + w.claims }),
    { videos: 0, claims: 0 }
  );

  return (
    <div>
      <PageHeader
        eyebrow="step 03"
        title="Research"
        description={
          workspaces.length
            ? `${workspaces.length} workspace${workspaces.length === 1 ? "" : "s"} · ${totals.videos} sources · ${totals.claims} claims`
            : "Each workspace collects related videos so claims can be compared across them."
        }
        actions={
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            <Plus className="h-3 w-3" />
            Add source
          </Link>
        }
      />

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-[124px] animate-pulse rounded-md border border-border bg-card/40"
            />
          ))}
        </div>
      ) : workspaces.length === 0 ? (
        <EmptyState
          title="no research yet"
          description="Add a YouTube video and it will be transcribed, mined for claims, and written up as a cited brief."
          action={{ label: "Add your first source", to: "/" }}
        />
      ) : (
        <WorkspaceGrid workspaces={workspaces} />
      )}
    </div>
  );
}
