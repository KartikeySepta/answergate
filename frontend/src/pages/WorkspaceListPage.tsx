import { Link } from "react-router-dom";
import { Library, Video, Lightbulb, FileText, Trash2, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useWorkspaces, useDeleteWorkspace } from "@/hooks/useWorkspaces";

interface Workspace {
  id: string;
  videos: number;
  claims: number;
  has_report: boolean;
}

export function WorkspaceListPage() {
  const { data } = useWorkspaces();
  const deleteWorkspace = useDeleteWorkspace();
  const workspaces: Workspace[] = data?.workspaces ?? [];

  const handleDelete = (id: string) => {
    if (!confirm(`Delete workspace "${id}"? This cannot be undone.`)) return;
    deleteWorkspace.mutate(id, {
      onSuccess: () => toast.success(`Workspace "${id}" deleted`),
      onError: () => toast.error(`Failed to delete "${id}"`),
    });
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-4">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Library className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight">Research Library</h1>
        </div>
        <Link
          to="/research/new"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-foreground text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus className="h-4 w-4" />
          New
        </Link>
      </div>

      {workspaces.length === 0 ? (
        <div className="bg-white rounded-xl border border-border shadow-sm p-12 text-center space-y-4">
          <Library className="h-10 w-10 text-muted-foreground mx-auto" />
          <p className="text-muted-foreground">No workspaces yet</p>
          <Link
            to="/research/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:border-foreground/30 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Create your first workspace
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {workspaces.map((ws) => (
            <div
              key={ws.id}
              className="bg-white rounded-xl border border-border shadow-sm p-5 flex flex-col justify-between hover:shadow-md transition-shadow"
            >
              <Link to={`/research/${ws.id}`} className="space-y-3 flex-1">
                <h2 className="text-lg font-medium truncate">{ws.id}</h2>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Video className="h-4 w-4" />
                    {ws.videos} video{ws.videos !== 1 && "s"}
                  </span>
                  <span className="flex items-center gap-1">
                    <Lightbulb className="h-4 w-4" />
                    {ws.claims} claim{ws.claims !== 1 && "s"}
                  </span>
                </div>
                {ws.has_report && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded-full">
                    <FileText className="h-3 w-3" />
                    Report ready
                  </span>
                )}
              </Link>
              <div className="mt-4 pt-3 border-t border-border flex justify-end">
                <button
                  onClick={() => handleDelete(ws.id)}
                  className={cn(
                    "p-2 rounded-lg text-muted-foreground hover:text-red-600 hover:bg-red-50 transition-colors",
                    deleteWorkspace.isPending && "opacity-50 pointer-events-none"
                  )}
                  aria-label={`Delete ${ws.id}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
