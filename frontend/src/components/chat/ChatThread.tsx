import { useEffect, useMemo, useRef } from "react";
import Markdown from "react-markdown";
import { CitationChip } from "./CitationChip";
import { MicroLabel } from "@/components/ui/primitives";

/*
 * Transcript-style thread, not chat bubbles.
 *
 * Answers here are cited prose that people read closely and re-read, so they
 * get full column width and a speaker label in the margin. Bubbles would cap
 * the line length and make a long, evidence-dense answer harder to scan.
 *
 * Answers arrive as Markdown (the model uses bullets and bold headings), so they
 * are rendered as Markdown — otherwise `**Job Invitations:**` shows up literally.
 * Citations are woven in during that render rather than before it: replacing
 * [Source 2] with a component *before* parsing would mean serialising a React
 * element into a string, so instead the Markdown renderer hands us its text
 * nodes and we split those.
 */

export interface ChatSource {
  video_title: string;
  timestamp: string;
}

export interface ChatMessage {
  role: string;
  content: string;
  mode?: string;
  /* Sources are stored on the message, not held in one shared "latest" map, so
     older turns keep working citations after a newer answer arrives. Turns
     restored from messages.json have none — the CLI persists only role/content,
     so those render as plain bracket text, which is honest: we cannot resolve
     what they point at. */
  sources?: Record<string, ChatSource>;
  verified?: boolean;
  caveat?: string | null;
}

export function ChatThread({
  messages,
  isLoading,
}: {
  messages: ChatMessage[];
  isLoading: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, isLoading]);

  return (
    <div className="space-y-7">
      {messages.map((m, i) => (
        <article key={i}>
          <div className="mb-1.5 flex items-center gap-2">
            <MicroLabel className={m.role === "user" ? "text-foreground/70" : "text-primary"}>
              {m.role === "user" ? "you" : "answer"}
            </MicroLabel>
            {m.role === "assistant" && m.verified && (
              <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-success">
                citations verified
              </span>
            )}
            {m.role === "assistant" && m.mode === "assist" && (
              <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary/80">
                assist
              </span>
            )}
          </div>

          {m.role === "user" ? (
            <p className="border-l-2 border-border pl-3 text-[13.5px] leading-relaxed text-foreground/80">
              {m.content}
            </p>
          ) : (
            <div>
              <Answer text={m.content} sources={m.sources ?? {}} />
              {m.caveat && (
                <p className="mt-3 border-l-2 border-l-primary bg-card/40 py-2 pl-3 text-[12px] leading-relaxed text-muted-foreground">
                  {m.caveat}
                </p>
              )}
            </div>
          )}
        </article>
      ))}

      {isLoading && (
        <div>
          <MicroLabel className="mb-1.5 block text-primary">answer</MicroLabel>
          <div className="flex items-center gap-1.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1 w-1 animate-bounce rounded-full bg-primary/60"
                style={{ animationDelay: `${i * 140}ms` }}
              />
            ))}
            <span className="ml-1.5 text-[12px] text-muted-foreground">
              retrieving passages, checking citations…
            </span>
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}

/* ── ANSWER RENDERING ─────────────────────────────────────────────────────── */

function Answer({
  text,
  sources,
}: {
  text: string;
  sources: Record<string, ChatSource>;
}) {
  // Rebuilding these on every keystroke elsewhere would re-parse every prior
  // answer, so memoise on the inputs that actually change the output.
  const components = useMemo(() => {
    const withCitations = (children: React.ReactNode) =>
      mapText(children, (s) => splitCitations(s, sources));

    return {
      p: ({ children }: { children?: React.ReactNode }) => (
        <p className="mb-3 last:mb-0">{withCitations(children)}</p>
      ),
      li: ({ children }: { children?: React.ReactNode }) => (
        <li className="mb-1">{withCitations(children)}</li>
      ),
      strong: ({ children }: { children?: React.ReactNode }) => (
        <strong className="font-medium text-foreground">{withCitations(children)}</strong>
      ),
      em: ({ children }: { children?: React.ReactNode }) => (
        <em className="italic">{withCitations(children)}</em>
      ),
      ul: ({ children }: { children?: React.ReactNode }) => (
        <ul className="mb-3 space-y-0.5 pl-4 [&_li]:list-disc [&_li]:marker:text-muted-foreground/40">
          {children}
        </ul>
      ),
      ol: ({ children }: { children?: React.ReactNode }) => (
        <ol className="mb-3 space-y-0.5 pl-4 [&_li]:list-decimal [&_li]:marker:text-muted-foreground/40">
          {children}
        </ol>
      ),
      h1: ({ children }: { children?: React.ReactNode }) => (
        <p className="mb-2 mt-4 font-medium text-foreground">{withCitations(children)}</p>
      ),
      h2: ({ children }: { children?: React.ReactNode }) => (
        <p className="mb-2 mt-4 font-medium text-foreground">{withCitations(children)}</p>
      ),
      h3: ({ children }: { children?: React.ReactNode }) => (
        <p className="mb-1.5 mt-3 font-medium text-foreground">{withCitations(children)}</p>
      ),
      code: ({ children }: { children?: React.ReactNode }) => (
        <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11.5px]">{children}</code>
      ),
      blockquote: ({ children }: { children?: React.ReactNode }) => (
        <blockquote className="mb-3 border-l-2 border-l-primary/40 bg-primary/[0.04] py-1.5 pl-3 text-muted-foreground">
          {children}
        </blockquote>
      ),
      a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="text-primary underline-offset-2 hover:underline"
        >
          {children}
        </a>
      ),
    };
  }, [sources]);

  return (
    <div className="text-[13.5px] leading-[1.75] text-foreground">
      <Markdown components={components}>{text}</Markdown>
    </div>
  );
}

/* Walk a rendered children tree and transform only the string leaves, leaving
   nested elements (bold inside a bullet, etc.) intact. */
function mapText(
  children: React.ReactNode,
  fn: (s: string) => React.ReactNode
): React.ReactNode {
  if (typeof children === "string") return fn(children);
  if (Array.isArray(children))
    return children.map((c, i) =>
      typeof c === "string" ? <span key={i}>{fn(c)}</span> : c
    );
  return children;
}

/*
 * Splits a run of text on [Source N] and grouped [Source 1, Source 2] markers.
 * A label with no matching entry in `sources` is left as plain text rather than
 * rendered as a chip — a citation you cannot open should not look openable.
 */
function splitCitations(
  text: string,
  sources: Record<string, ChatSource>
): React.ReactNode {
  const re = /\[((?:Source\s*\d+\s*(?:,\s*)?)+)\]/gi;
  const out: React.ReactNode[] = [];
  let last = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) out.push(text.slice(last, match.index));

    const chips = match[1]
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((raw) => resolve(raw, sources))
      .filter((k): k is string => k !== null)
      .map((k) => (
        <CitationChip
          key={key++}
          label={k}
          videoTitle={sources[k].video_title}
          timestamp={sources[k].timestamp}
        />
      ));

    out.push(chips.length ? <span key={key++}>{chips}</span> : match[0]);
    last = re.lastIndex;
  }

  if (last < text.length) out.push(text.slice(last));
  return out.length ? out : text;
}

/* Source keys come from the backend verbatim ("Source 1"); match tolerantly on
   case and spacing without inventing keys that don't exist. */
function resolve(raw: string, sources: Record<string, ChatSource>): string | null {
  if (sources[raw]) return raw;
  const want = raw.toLowerCase().replace(/\s+/g, " ");
  return (
    Object.keys(sources).find(
      (k) => k.toLowerCase().replace(/\s+/g, " ") === want
    ) ?? null
  );
}
