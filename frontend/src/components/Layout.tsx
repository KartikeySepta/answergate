import { Link, Outlet, useLocation } from "react-router-dom";
import { useJobs } from "@/hooks/useJobs";
import { cn } from "@/lib/utils";
import { MicroLabel } from "@/components/ui/primitives";

/*
 * Shell: a fixed left rail, content on a warm dark page.
 *
 * The rail is text-first and numbered rather than icon-led. Icons would imply
 * these are tools; the numbers imply a sequence, which is what this actually is
 * — you add sources, watch them process, then read the result.
 */

const nav = [
  { to: "/", label: "Add source", step: 1 },
  { to: "/jobs", label: "Processing", step: 2 },
  { to: "/workspaces", label: "Research", step: 3 },
] as const;

export function Layout() {
  const { pathname } = useLocation();
  // Live queue count in the rail — the pipeline is serial, so knowing something
  // is running elsewhere is the difference between "slow" and "waiting its turn".
  const { data: jobsData } = useJobs();
  const running = jobsData?.jobs.filter(
    (j) => j.status === "running" || j.status === "queued"
  ).length;

  const isActive = (to: string) =>
    to === "/" ? pathname === "/" : pathname.startsWith(to);

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[212px] flex-col border-r border-border bg-card md:flex">
        {/* Wordmark */}
        <div className="px-5 pb-6 pt-6">
          <Link to="/" className="block">
            <div className="font-mono text-[13px] font-medium tracking-tight text-foreground">
              evidence
              <span className="text-primary">/</span>
              base
            </div>
            <MicroLabel className="mt-1 block">cited video research</MicroLabel>
          </Link>
        </div>

        <nav className="flex-1 px-2">
          {nav.map(({ to, label, step }) => {
            const active = isActive(to);
            return (
              <Link
                key={to}
                to={to}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative flex items-baseline gap-3 rounded-md px-3 py-2.5 transition-colors",
                  active ? "bg-accent" : "hover:bg-accent/40"
                )}
              >
                {/* Active marker: a highlighter tick in the margin */}
                <span
                  aria-hidden
                  className={cn(
                    "absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full transition-colors",
                    active ? "bg-primary" : "bg-transparent"
                  )}
                />
                <span
                  className={cn(
                    "tabular font-mono text-[10px]",
                    active ? "text-primary" : "text-muted-foreground/50"
                  )}
                >
                  {String(step).padStart(2, "0")}
                </span>
                <span
                  className={cn(
                    "text-[13px] leading-none",
                    active
                      ? "font-medium text-foreground"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                >
                  {label}
                </span>
                {to === "/jobs" && running ? (
                  <span className="tabular ml-auto font-mono text-[10px] text-primary">
                    {running}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-3 border-t border-border px-5 py-4">
          <Link
            to="/settings"
            className={cn(
              "block text-[12px] transition-colors",
              pathname.startsWith("/settings")
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Settings
          </Link>
          <p className="font-mono text-[10px] text-muted-foreground/60">
            local · single worker
          </p>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-40 flex items-center gap-4 border-b border-border bg-card px-4 py-3 md:hidden">
        <Link to="/" className="font-mono text-[13px] font-medium">
          evidence<span className="text-primary">/</span>base
        </Link>
        <nav className="ml-auto flex items-center gap-3">
          {nav.map(({ to, step }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "tabular font-mono text-[11px]",
                isActive(to) ? "text-primary" : "text-muted-foreground"
              )}
            >
              {String(step).padStart(2, "0")}
            </Link>
          ))}
          <Link
            to="/settings"
            className={cn(
              "font-mono text-[11px]",
              pathname.startsWith("/settings") ? "text-primary" : "text-muted-foreground"
            )}
          >
            ··
          </Link>
        </nav>
      </div>

      <main className="md:ml-[212px]">
        <div className="mx-auto max-w-3xl px-5 py-10 md:px-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
