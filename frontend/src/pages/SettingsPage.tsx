import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Eye, EyeOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/health";
import { Input } from "@/components/ui/input";
import { Field, MicroLabel, Mono, PageHeader, Section } from "@/components/ui/primitives";

const STORAGE_KEY = "yt-ai-api-key";
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function SettingsPage() {
  const [key, setKey] = useState("");
  const [reveal, setReveal] = useState(false);

  useEffect(() => {
    setKey(localStorage.getItem(STORAGE_KEY) ?? "");
  }, []);

  // Health tells us whether the backend even wants a key, which turns this from
  // a mystery field into an answerable question.
  const { data: health, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 15_000,
  });

  function save() {
    const v = key.trim();
    if (v) localStorage.setItem(STORAGE_KEY, v);
    else localStorage.removeItem(STORAGE_KEY);
    toast.success(v ? "Key saved" : "Key cleared");
  }

  return (
    <div>
      <PageHeader
        eyebrow="settings"
        title="Connection"
        description="How this browser talks to your local research backend."
      />

      <div className="space-y-9">
        <Section label="backend">
          <dl className="divide-y divide-border border-y border-border">
            <Row label="endpoint">
              <Mono>{API_BASE}</Mono>
            </Row>
            <Row label="reachable">
              {isError ? (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-destructive" />
                  <Mono>no — is uvicorn running?</Mono>
                </span>
              ) : health ? (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  <Mono>yes</Mono>
                </span>
              ) : (
                <Mono dim>checking…</Mono>
              )}
            </Row>
            <Row label="auth">
              <Mono dim>
                {health
                  ? health.auth_required
                    ? "required — a key must be set below"
                    : "open — no API_KEY set on the server"
                  : "—"}
              </Mono>
            </Row>
            <Row label="queue">
              <Mono dim>{health ? `${health.queue_depth} waiting` : "—"}</Mono>
            </Row>
          </dl>
        </Section>

        <Section label="credentials">
          <Field
            label="API key"
            htmlFor="key"
            hint="Sent as X-API-Key on requests that create, chat, or delete. Only needed when the server sets API_KEY."
          >
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="key"
                  type={reveal ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="leave empty if the server has no API_KEY"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="pr-9 font-mono text-[13px]"
                />
                <button
                  type="button"
                  onClick={() => setReveal((v) => !v)}
                  aria-label={reveal ? "Hide key" : "Show key"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
              <button
                onClick={save}
                className="shrink-0 rounded-md bg-primary px-3 py-2 text-[12px] font-medium text-primary-foreground hover:opacity-90"
              >
                Save
              </button>
            </div>
          </Field>

          {/*
            Stated plainly rather than buried: localStorage is readable by any
            script on this origin. Fine for a tool you run yourself, not fine as
            the auth story for something on the public internet.
          */}
          <p className="border-l-2 border-l-border py-2 pl-3 text-[12px] leading-relaxed text-muted-foreground">
            The key is stored in this browser's localStorage. That is appropriate
            for a local, single-operator tool. It is not sufficient for a
            deployment other people can reach — that needs real per-user
            accounts and a server-side session.
          </p>
        </Section>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <MicroLabel as="div">{label}</MicroLabel>
      <dd className="min-w-0 truncate text-right">{children}</dd>
    </div>
  );
}
