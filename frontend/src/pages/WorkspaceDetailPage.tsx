import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import Markdown from "react-markdown";
import {
  FileText, MessageSquare, ListChecks, GitCompare, Video,
  Send, CheckCircle2, AlertTriangle, Clock, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useWorkspace } from "@/hooks/useWorkspaces";
import { useClaims, useThemes, useReport } from "@/hooks/useClaims";
import { useMessages, useSendMessage } from "@/hooks/useChat";
import type { Claim, Theme, WorkspaceVideo } from "@/api/types";
import { cn } from "@/lib/utils";

type Tab = "overview" | "ask" | "claims" | "compare" | "sources";
const TABS: { value: Tab; label: string; icon: React.ReactNode }[] = [
  { value: "overview", label: "Overview", icon: <FileText className="h-4 w-4" /> },
  { value: "ask", label: "Ask AI", icon: <MessageSquare className="h-4 w-4" /> },
  { value: "claims", label: "Claims", icon: <ListChecks className="h-4 w-4" /> },
  { value: "compare", label: "Compare", icon: <GitCompare className="h-4 w-4" /> },
  { value: "sources", label: "Sources", icon: <Video className="h-4 w-4" /> },
];
const PAGE_SIZE = 20;

export function WorkspaceDetailPage() {
  const { id = "" } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("overview");
  const { data: ws, isLoading } = useWorkspace(id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="h-8 w-48 animate-pulse rounded-xl bg-gray-100" />
        <div className="mt-4 h-4 w-72 animate-pulse rounded-xl bg-gray-100" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">{id}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-500">
          <span className="flex items-center gap-1.5">
            <Video className="h-3.5 w-3.5" />
            {ws?.videos.length ?? 0} videos
          </span>
          <span className="flex items-center gap-1.5">
            <ListChecks className="h-3.5 w-3.5" />
            {ws?.claim_count ?? 0} claims
          </span>
          <span className="flex items-center gap-1.5">
            <GitCompare className="h-3.5 w-3.5" />
            {ws?.theme_count ?? 0} themes
          </span>
          <span className={cn(
            "flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
            ws?.has_report
              ? "bg-emerald-50 text-emerald-700"
              : "bg-gray-100 text-gray-500"
          )}>
            {ws?.has_report ? "Report ready" : "No report"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all",
              tab === t.value
                ? "bg-white text-cobalt-600 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {tab === "overview" && <OverviewTab id={id} />}
        {tab === "ask" && <AskTab id={id} />}
        {tab === "claims" && <ClaimsTab id={id} />}
        {tab === "compare" && <CompareTab id={id} />}
        {tab === "sources" && <SourcesTab videos={ws?.videos ?? []} />}
      </div>
    </div>
  );
}

/* ── OVERVIEW ──────────────────────────────────────────────────────────────── */

function OverviewTab({ id }: { id: string }) {
  const { data, isLoading, error } = useReport(id);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[90, 70, 100, 80].map((w, i) => (
          <div key={i} className="h-3 animate-pulse rounded bg-gray-100" style={{ width: `${w}%` }} />
        ))}
      </div>
    );
  }

  if (error || !data?.markdown) {
    return (
      <div className="py-12 text-center">
        <FileText className="mx-auto h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-600">No report yet</p>
        <p className="mt-1 text-xs text-gray-400">The report generates after all sources are processed.</p>
      </div>
    );
  }

  return (
    <article className={cn(
      "prose prose-sm max-w-none text-gray-700",
      "[&_h1]:text-lg [&_h1]:font-semibold [&_h1]:text-gray-900",
      "[&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-gray-900",
      "[&_h3]:text-sm [&_h3]:font-medium [&_h3]:text-gray-700",
      "[&_a]:text-blue-600 [&_a]:no-underline hover:[&_a]:underline",
      "[&_blockquote]:border-l-2 [&_blockquote]:border-blue-200 [&_blockquote]:bg-blue-50/50 [&_blockquote]:pl-3",
      "[&_code]:rounded [&_code]:bg-gray-100 [&_code]:px-1 [&_code]:text-xs"
    )}>
      <Markdown>{data.markdown}</Markdown>
    </article>
  );
}

/* ── ASK AI ────────────────────────────────────────────────────────────────── */

const SUGGESTED = [
  "What are the main takeaways?",
  "Where do the sources disagree?",
  "Summarize the key recommendations.",
];

function AskTab({ id }: { id: string }) {
  const [mode, setMode] = useState<"grounded" | "assist">("grounded");
  const [question, setQuestion] = useState("");
  const [local, setLocal] = useState<{ role: string; content: string; mode?: string; verified?: boolean; sources?: Record<string, unknown> }[]>([]);
  const [seeded, setSeeded] = useState(false);

  const { data: persisted } = useMessages(id);
  const send = useSendMessage();

  useEffect(() => {
    if (seeded || !persisted) return;
    setLocal(persisted.messages);
    setSeeded(true);
  }, [persisted, seeded]);

  const history = useMemo(
    () => local.map((m) => ({ role: m.role, content: m.content })),
    [local]
  );

  function submit(q?: string) {
    const text = (q ?? question).trim();
    if (!text || send.isPending) return;
    setLocal((prev) => [...prev, { role: "user", content: text, mode }]);
    setQuestion("");
    send.mutate(
      { workspaceId: id, question: text, history, mode },
      {
        onSuccess: (res) =>
          setLocal((prev) => [...prev, {
            role: "assistant", content: res.answer, mode: res.mode,
            verified: res.verified, sources: res.sources,
          }]),
        onError: () => setLocal((prev) => prev.slice(0, -1)),
      }
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        {(["grounded", "assist"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-all",
              mode === m ? "bg-blue-600 text-white shadow-sm" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {m}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="max-h-[400px] min-h-[200px] space-y-3 overflow-y-auto">
        {local.length === 0 && !send.isPending ? (
          <div className="py-10 text-center">
            <MessageSquare className="mx-auto h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm text-gray-500">Ask anything about your sources</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-blue-300 hover:text-blue-600"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          local.map((msg, i) => (
            <div key={i} className={cn(
              "rounded-xl px-4 py-3 text-sm",
              msg.role === "user" ? "ml-auto max-w-[80%] bg-blue-600 text-white" : "mr-auto max-w-[90%] bg-gray-50 text-gray-800 border border-gray-200"
            )}>
              {msg.role === "user" ? (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <AssistantMessage content={msg.content} sources={msg.sources} />
              )}
              {msg.role === "assistant" && msg.verified && (
                <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                  <CheckCircle2 className="h-3 w-3" /> Verified
                </span>
              )}
            </div>
          ))
        )}
        {send.isPending && (
          <div className="mr-auto max-w-[85%] animate-pulse rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-400">
            Thinking…
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="flex items-end gap-2">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          rows={1}
          placeholder="Ask about these sources…"
          className="flex-1 resize-none rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm outline-none placeholder:text-gray-400 focus:border-blue-300 focus:ring-1 focus:ring-blue-100"
        />
        <button
          type="submit"
          disabled={!question.trim() || send.isPending}
          className="rounded-xl bg-blue-600 p-3 text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}

/* ── CLAIMS ────────────────────────────────────────────────────────────────── */

const TYPE_COLORS: Record<string, string> = {
  fact: "bg-blue-50 text-blue-700",
  opinion: "bg-purple-50 text-purple-700",
  prediction: "bg-amber-50 text-amber-700",
  warning: "bg-red-50 text-red-700",
  recommendation: "bg-emerald-50 text-emerald-700",
};
const STANCE_ICON: Record<string, React.ReactNode> = {
  support: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />,
  oppose: <AlertTriangle className="h-3.5 w-3.5 text-red-500" />,
  neutral: <Clock className="h-3.5 w-3.5 text-gray-400" />,
  mixed: <GitCompare className="h-3.5 w-3.5 text-amber-500" />,
};

function ClaimsTab({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<string>("all");
  const { data, isLoading, error } = useClaims(id, PAGE_SIZE, offset);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-50" />
        ))}
      </div>
    );
  }

  if (error || !data || data.total === 0) {
    return (
      <div className="py-12 text-center">
        <ListChecks className="mx-auto h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-600">No claims extracted yet</p>
        <p className="mt-1 text-xs text-gray-400">Claims appear after sources are fully processed.</p>
      </div>
    );
  }

  const types = ["all", "fact", "opinion", "prediction", "warning", "recommendation"];
  const filtered = filter === "all" ? data.claims : data.claims.filter((c) => c.claim_type === filter);

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={cn(
              "rounded-lg px-3 py-1 text-xs font-medium capitalize transition",
              filter === t ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="space-y-3">
        {filtered.map((claim) => (
          <ClaimItem key={claim.claim_id} claim={claim} />
        ))}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between border-t border-gray-100 pt-4">
        <span className="text-xs text-gray-500">
          {data.offset + 1}–{Math.min(data.offset + data.limit, data.total)} of {data.total}
        </span>
        <div className="flex gap-2">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-blue-300 disabled:opacity-40"
          >
            <ChevronLeft className="h-3 w-3" /> Prev
          </button>
          <button
            disabled={data.offset + data.limit >= data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-blue-300 disabled:opacity-40"
          >
            Next <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ClaimItem({ claim }: { claim: Claim }) {
  return (
    <div className="rounded-xl border border-gray-200 p-4 transition hover:shadow-sm">
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{STANCE_ICON[claim.stance] ?? STANCE_ICON.neutral}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", TYPE_COLORS[claim.claim_type] ?? "bg-gray-100 text-gray-600")}>
              {claim.claim_type}
            </span>
            <span className="text-[10px] text-gray-400">{claim.stance}</span>
          </div>
          <p className="text-sm text-gray-800">{claim.claim}</p>
          {claim.evidence.length > 0 && (
            <p className="mt-2 text-xs leading-relaxed text-gray-500 line-clamp-2">
              {claim.evidence[0].evidence_text}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── COMPARE ───────────────────────────────────────────────────────────────── */

const REL_COLORS: Record<string, string> = {
  agreement: "border-l-emerald-500 bg-emerald-50/50",
  contradiction: "border-l-red-500 bg-red-50/50",
  partial_agreement: "border-l-blue-500 bg-blue-50/50",
  different_context: "border-l-amber-500 bg-amber-50/50",
  independent: "border-l-gray-400 bg-gray-50",
  related: "border-l-gray-400 bg-gray-50",
};
const REL_BADGE: Record<string, string> = {
  agreement: "bg-emerald-100 text-emerald-700",
  contradiction: "bg-red-100 text-red-700",
  partial_agreement: "bg-blue-100 text-blue-700",
  different_context: "bg-amber-100 text-amber-700",
  independent: "bg-gray-100 text-gray-600",
  related: "bg-gray-100 text-gray-600",
};

function CompareTab({ id }: { id: string }) {
  const { data, isLoading } = useThemes(id);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-50" />
        ))}
      </div>
    );
  }

  const themes = data?.themes ?? [];

  if (themes.length === 0) {
    return (
      <div className="py-12 text-center">
        <GitCompare className="mx-auto h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-600">No cross-source themes yet</p>
        <p className="mt-1 text-xs text-gray-400">Add multiple sources to discover agreements and contradictions.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {themes.map((theme) => (
        <ThemeItem key={theme.theme_id} theme={theme} />
      ))}
    </div>
  );
}

function ThemeItem({ theme }: { theme: Theme }) {
  return (
    <div className={cn("rounded-xl border-l-4 p-4", REL_COLORS[theme.relationship] ?? REL_COLORS.related)}>
      <div className="flex items-center gap-2 mb-2">
        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", REL_BADGE[theme.relationship] ?? REL_BADGE.related)}>
          {theme.relationship.replace("_", " ")}
        </span>
        <span className="text-[10px] text-gray-400">
          cosine: {theme.cosine.toFixed(3)}
        </span>
      </div>
      <p className="text-sm text-gray-800">{theme.synthesis_note}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {theme.videos.map((vid) => (
          <span key={vid} className="rounded-md bg-white px-2 py-0.5 text-[10px] text-gray-500 border border-gray-200">
            {vid}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── SOURCES ───────────────────────────────────────────────────────────────── */

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function SourcesTab({ videos }: { videos: WorkspaceVideo[] }) {
  if (videos.length === 0) {
    return (
      <div className="py-12 text-center">
        <Video className="mx-auto h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-600">No sources added</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {videos.map((v) => (
        <div key={v.video_id} className="overflow-hidden rounded-xl border border-gray-200 transition hover:shadow-sm">
          <img
            src={`https://img.youtube.com/vi/${v.video_id}/mqdefault.jpg`}
            alt={v.title ?? v.video_id}
            className="h-36 w-full object-cover"
          />
          <div className="p-3">
            <p className="text-sm font-medium text-gray-800 line-clamp-2">{v.title ?? v.video_id}</p>
            <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-500">
              {v.channel && <span>{v.channel}</span>}
              <span>{formatDuration(v.duration_seconds)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default WorkspaceDetailPage;

/* ── ASSISTANT MESSAGE (Markdown + Citation Chips) ─────────────────────────── */

/**
 * Renders assistant messages with full Markdown and styled citation chips.
 * Citations like [Source 1] or [Source 2, Source 3] become colored pills.
 */
function AssistantMessage({ content, sources }: { content: string; sources?: Record<string, unknown> }) {
  return (
    <div className={cn(
      "assistant-message text-[13.5px] leading-relaxed",
      "[&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-gray-900",
      "[&_h2]:mt-3.5 [&_h2]:mb-1.5 [&_h2]:text-[13.5px] [&_h2]:font-semibold [&_h2]:text-gray-900",
      "[&_h3]:mt-3 [&_h3]:mb-1 [&_h3]:text-[13px] [&_h3]:font-medium [&_h3]:text-gray-800",
      "[&_p]:mb-2.5 [&_p]:last:mb-0",
      "[&_ul]:mb-2.5 [&_ul]:ml-4 [&_ul]:space-y-1.5 [&_li]:list-disc [&_li]:marker:text-blue-400",
      "[&_ol]:mb-2.5 [&_ol]:ml-4 [&_ol]:space-y-1.5 [&_ol>li]:list-decimal",
      "[&_strong]:font-semibold [&_strong]:text-gray-900",
      "[&_em]:italic",
      "[&_code]:rounded [&_code]:bg-gray-100 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_code]:text-gray-700",
      "[&_pre]:my-3 [&_pre]:rounded-lg [&_pre]:bg-gray-900 [&_pre]:p-3 [&_pre]:text-xs [&_pre]:text-gray-100 [&_pre]:overflow-x-auto",
      "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-inherit",
      "[&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:border-blue-200 [&_blockquote]:bg-blue-50/40 [&_blockquote]:py-1.5 [&_blockquote]:pl-3 [&_blockquote]:text-gray-600 [&_blockquote]:italic",
      "[&_hr]:my-4 [&_hr]:border-gray-200",
    )}>
      <Markdown
        components={{
          // Override text nodes to inject citation chips
          p: ({ children }) => <p>{renderWithCitations(children, sources)}</p>,
          li: ({ children }) => <li>{renderWithCitations(children, sources)}</li>,
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}

/**
 * Takes React children from a Markdown node and replaces [Source N] patterns
 * with styled citation chip components.
 */
function renderWithCitations(children: React.ReactNode, sources?: Record<string, unknown>): React.ReactNode {
  if (!children) return children;

  // Process each child — only transform strings
  const processed = Array.isArray(children)
    ? children.map((child, idx) => processChild(child, idx, sources))
    : processChild(children, 0, sources);

  return processed;
}

function processChild(child: React.ReactNode, key: number, sources?: Record<string, unknown>): React.ReactNode {
  if (typeof child !== "string") return child;

  // Split on citation patterns: [Source N] or [Source N, Source M, ...]
  const parts = child.split(/(\[Source\s+\d+(?:\s*,\s*Source\s+\d+)*\])/g);

  if (parts.length === 1) return child; // No citations found

  return parts.map((part, i) => {
    const citationMatch = part.match(/^\[Source\s+(.+)\]$/);
    if (!citationMatch) return part;

    // Extract individual source numbers
    const sourceRefs = citationMatch[1].split(/\s*,\s*Source\s*/i);

    return (
      <span key={`${key}-${i}`} className="inline-flex items-center gap-0.5 mx-0.5">
        {sourceRefs.map((num, si) => (
          <CitationChip
            key={si}
            number={num.trim()}
            source={sources?.[num.trim()] as { video_title?: string; timestamp?: string } | undefined}
          />
        ))}
      </span>
    );
  });
}

function CitationChip({ number, source }: { number: string; source?: { video_title?: string; timestamp?: string } }) {
  return (
    <span
      className="group relative inline-flex items-center gap-0.5 rounded-md bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 cursor-default transition-colors hover:bg-blue-200"
      title={source ? `${source.video_title ?? "Source"} @ ${source.timestamp ?? ""}` : `Source ${number}`}
    >
      <svg className="h-2.5 w-2.5" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 8.5V4a2 2 0 012-2h2a2 2 0 012 2v4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <path d="M2 8.5h8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <circle cx="6" cy="10" r="0.8" fill="currentColor"/>
      </svg>
      {number}
      {/* Tooltip on hover */}
      {source && (
        <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md bg-gray-900 px-2.5 py-1.5 text-[10px] font-normal text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
          {source.video_title ?? `Source ${number}`}
          {source.timestamp && (
            <span className="ml-1.5 text-gray-400">@ {source.timestamp}</span>
          )}
        </span>
      )}
    </span>
  );
}

