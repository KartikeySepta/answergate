import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Markdown from "react-markdown";
import { ArrowRight, Plus, Send, Trash2 } from "lucide-react";
import { useWorkspace, useDeleteWorkspace } from "@/hooks/useWorkspaces";
import { useClaims, useThemes, useReport } from "@/hooks/useClaims";
import { useMessages, useSendMessage } from "@/hooks/useChat";
import { ChatThread, type ChatMessage } from "@/components/chat/ChatThread";
import { ModeToggle } from "@/components/chat/ModeToggle";
import { ClaimCard } from "@/components/claims/ClaimCard";
import { ThemeCard } from "@/components/claims/ThemeCard";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  EmptyState,
  MicroLabel,
  Mono,
  PageHeader,
  Segmented,
  Stat,
} from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

type Tab = "brief" | "ask" | "claims" | "themes";
const PAGE_SIZE = 20;

export function WorkspaceDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("brief");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: ws, isLoading } = useWorkspace(id);
  const del = useDeleteWorkspace();

  return (
    <div>
      <PageHeader
        eyebrow="research"
        title={id}
        description={
          ws
            ? ws.videos
                .map((v) => v.title ?? v.video_id)
                .slice(0, 2)
                .join(" · ") + (ws.videos.length > 2 ? ` · +${ws.videos.length - 2} more` : "")
            : undefined
        }
        actions={
          <>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[12px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              <Plus className="h-3 w-3" />
              Add source
            </Link>
            <button
              onClick={() => setConfirmDelete(true)}
              aria-label="Delete workspace"
              className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </>
        }
      />

      {/* Counts */}
      <div className="mb-7 flex flex-wrap gap-8 border-b border-border pb-6">
        {isLoading || !ws ? (
          <div className="h-9 w-64 animate-pulse rounded bg-muted" />
        ) : (
          <>
            <Stat value={ws.videos.length} label={ws.videos.length === 1 ? "source" : "sources"} />
            <Stat value={ws.claim_count} label="claims" />
            <Stat value={ws.theme_count} label="cross-source" accent={ws.theme_count > 0} />
            <Stat value={ws.has_report ? "yes" : "—"} label="brief" />
          </>
        )}
      </div>

      <div className="mb-6">
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { value: "brief", label: "Brief" },
            { value: "ask", label: "Ask" },
            { value: "claims", label: "Claims" },
            { value: "themes", label: "Cross-source" },
          ]}
        />
      </div>

      {tab === "brief" && <BriefTab id={id} />}
      {tab === "ask" && <AskTab id={id} />}
      {tab === "claims" && <ClaimsTab id={id} />}
      {tab === "themes" && <ThemesTab id={id} />}

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {id}?</DialogTitle>
          </DialogHeader>
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            This removes the transcripts, claims, brief, conversation, and vector
            index for this workspace. It cannot be undone — you would need to
            re-process every source.
          </p>
          <DialogFooter>
            <button
              onClick={() => setConfirmDelete(false)}
              className="rounded-md border border-border px-3 py-1.5 text-[12px] text-muted-foreground hover:text-foreground"
            >
              Keep it
            </button>
            <button
              disabled={del.isPending}
              onClick={() =>
                del.mutate(id, {
                  onSuccess: () => {
                    toast.success(`Deleted ${id}`);
                    navigate("/workspaces");
                  },
                  onError: (e) => toast.error(e.message),
                })
              }
              className="rounded-md bg-destructive px-3 py-1.5 text-[12px] font-medium text-destructive-foreground hover:opacity-90 disabled:opacity-50"
            >
              {del.isPending ? "Deleting…" : "Delete permanently"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ── BRIEF ─────────────────────────────────────────────────────────────────── */

function BriefTab({ id }: { id: string }) {
  const { data, isLoading, error } = useReport(id);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[90, 70, 100, 85, 60].map((w, i) => (
          <div
            key={i}
            className="h-3 animate-pulse rounded bg-muted"
            style={{ width: `${w}%` }}
          />
        ))}
      </div>
    );
  }

  if (error || !data?.markdown) {
    return (
      <EmptyState
        title="no brief yet"
        description="The brief is written at the end of the pipeline. If a source is still processing, it will appear when that finishes."
      />
    );
  }

  return (
    <article
      className={cn(
        "max-w-none text-[13.5px] leading-[1.75] text-foreground/90",
        // Typographic rhythm for the generated markdown
        "[&_h1]:mb-3 [&_h1]:mt-8 [&_h1]:text-[19px] [&_h1]:font-medium [&_h1]:tracking-tight [&_h1]:text-foreground",
        "[&_h2]:mb-2.5 [&_h2]:mt-7 [&_h2]:text-[15px] [&_h2]:font-medium [&_h2]:text-foreground",
        "[&_h3]:mb-2 [&_h3]:mt-5 [&_h3]:font-mono [&_h3]:text-[11px] [&_h3]:uppercase [&_h3]:tracking-[0.12em] [&_h3]:text-muted-foreground",
        "[&_p]:mb-3.5",
        "[&_ul]:mb-4 [&_ul]:space-y-1.5 [&_ul]:pl-4 [&_li]:list-disc [&_li]:marker:text-muted-foreground/40",
        "[&_ol]:mb-4 [&_ol]:space-y-1.5 [&_ol]:pl-4 [&_ol>li]:list-decimal",
        "[&_strong]:font-medium [&_strong]:text-foreground",
        "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[11.5px]",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-l-primary/40 [&_blockquote]:bg-primary/[0.04] [&_blockquote]:py-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
        "[&_a]:text-primary [&_a]:underline-offset-2 hover:[&_a]:underline",
        "[&_hr]:my-7 [&_hr]:border-border",
        "[&_table]:my-4 [&_table]:w-full [&_table]:text-[12.5px]",
        "[&_th]:border-b [&_th]:border-border [&_th]:pb-1.5 [&_th]:text-left [&_th]:font-mono [&_th]:text-[10px] [&_th]:uppercase [&_th]:tracking-[0.12em] [&_th]:text-muted-foreground",
        "[&_td]:border-b [&_td]:border-border/50 [&_td]:py-2 [&_td]:pr-4 [&_td]:align-top"
      )}
    >
      <Markdown>{data.markdown}</Markdown>
    </article>
  );
}

/* ── ASK ───────────────────────────────────────────────────────────────────── */

function AskTab({ id }: { id: string }) {
  const [mode, setMode] = useState<"grounded" | "assist">("grounded");
  const [question, setQuestion] = useState("");
  const [local, setLocal] = useState<ChatMessage[]>([]);
  const [seeded, setSeeded] = useState(false);

  const { data: persisted } = useMessages(id);
  const send = useSendMessage();

  // Seed once from persisted history; afterwards local state owns the thread so
  // an in-flight answer isn't clobbered by a refetch.
  useEffect(() => {
    if (seeded || !persisted) return;
    setLocal(persisted.messages as ChatMessage[]);
    setSeeded(true);
  }, [persisted, seeded]);

  // History sent to the backend must be plain role/content pairs.
  const history = useMemo(
    () => local.map((m) => ({ role: m.role, content: m.content })),
    [local]
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || send.isPending) return;

    setLocal((prev) => [...prev, { role: "user", content: q, mode }]);
    setQuestion("");

    send.mutate(
      { workspaceId: id, question: q, history, mode },
      {
        onSuccess: (res) =>
          setLocal((prev) => [
            ...prev,
            {
              role: "assistant",
              content: res.answer,
              mode: res.mode,
              sources: res.sources,
              verified: res.verified,
              caveat: res.caveat,
            },
          ]),
        onError: (err) => {
          toast.error(err.message || "Could not get an answer");
          setLocal((prev) => prev.slice(0, -1)); // roll back the optimistic user turn
          setQuestion(q);
        },
      }
    );
  }

  return (
    <div className="space-y-6">
      <ModeToggle mode={mode} onChange={setMode} />

      {local.length === 0 && !send.isPending ? (
        <EmptyState
          title="nothing asked yet"
          description="Ask about anything in these sources. In grounded mode every sentence is traced to a passage, and citations that don't check out are flagged."
        />
      ) : (
        <ChatThread messages={local} isLoading={send.isPending} />
      )}

      <form onSubmit={submit} className="sticky bottom-0 bg-background pt-2">
        <div className="flex items-end gap-2 rounded-md border border-border bg-card p-2 focus-within:border-primary/40">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) submit(e);
            }}
            rows={1}
            placeholder="Ask about these sources…"
            className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent text-[13px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/60"
          />
          <button
            type="submit"
            disabled={!question.trim() || send.isPending}
            aria-label="Send"
            className="shrink-0 rounded-md bg-primary p-1.5 text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
        <MicroLabel className="mt-1.5 block">
          enter to send · shift+enter for a new line
        </MicroLabel>
      </form>
    </div>
  );
}

/* ── CLAIMS ────────────────────────────────────────────────────────────────── */

function ClaimsTab({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useClaims(id, PAGE_SIZE, offset);

  if (isLoading) {
    return (
      <div className="divide-y divide-border border-y border-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2 py-4">
            <div className="h-2 w-24 animate-pulse rounded bg-muted" />
            <div className="h-3 w-full animate-pulse rounded bg-muted" />
            <div className="h-3 w-3/5 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    );
  }

  if (error || !data || data.total === 0) {
    return (
      <EmptyState
        title="no claims yet"
        description="Claims are extracted after indexing. Each one is kept only if its evidence points at a real passage."
      />
    );
  }

  const from = data.offset + 1;
  const to = Math.min(data.offset + data.limit, data.total);

  return (
    <div>
      <div className="divide-y divide-border border-y border-border">
        {data.claims.map((c) => (
          <ClaimCard key={c.claim_id} claim={c} />
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <MicroLabel>
          {from}–{to} of {data.total}
        </MicroLabel>
        <div className="flex gap-1.5">
          <PageBtn
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </PageBtn>
          <PageBtn disabled={to >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </PageBtn>
        </div>
      </div>
    </div>
  );
}

function PageBtn({
  children,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="rounded-md border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}

/* ── THEMES ────────────────────────────────────────────────────────────────── */

function ThemesTab({ id }: { id: string }) {
  const { data, isLoading } = useThemes(id);

  if (isLoading) {
    return (
      <div className="divide-y divide-border border-y border-border">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-2 py-4">
            <div className="h-2 w-20 animate-pulse rounded bg-muted" />
            <div className="h-3 w-4/5 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    );
  }

  const themes = data?.themes ?? [];

  if (themes.length === 0) {
    return (
      <EmptyState
        title="no cross-source themes"
        description="These appear once a workspace holds two or more sources — they mark where different creators agree, conflict, or are talking about different scopes."
        action={{ label: "Add another source", to: "/" }}
      />
    );
  }

  const conflicts = themes.filter((t) => t.relationship === "contradiction").length;

  return (
    <div>
      {conflicts > 0 && (
        <p className="mb-4 border-l-2 border-l-destructive bg-card/40 py-2 pl-3 text-[12.5px] text-muted-foreground">
          <span className="text-foreground">
            {conflicts} conflict{conflicts === 1 ? "" : "s"}
          </span>{" "}
          between sources — usually the most interesting thing in a workspace.
        </p>
      )}
      <div className="divide-y divide-border border-y border-border">
        {themes.map((t) => (
          <ThemeCard key={t.theme_id} theme={t} />
        ))}
      </div>
      <Link
        to="/"
        className="mt-4 inline-flex items-center gap-1.5 text-[12px] text-primary hover:underline"
      >
        Add another source to find more <ArrowRight className="h-3 w-3" />
      </Link>
      <Mono dim className="ml-2">
        {themes.length} pairs
      </Mono>
    </div>
  );
}
