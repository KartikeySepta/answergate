/*
 * Shared design primitives — the app's visual signature lives here.
 *
 * Every screen composes these instead of hand-rolling layout, which is what
 * keeps the "research notebook" language consistent: mono micro-labels for
 * metadata, a numbered left gutter for anything list-like, and hairline rules
 * instead of boxes wherever a box would add weight without adding meaning.
 */

import * as React from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

/* ── MICRO LABEL ────────────────────────────────────────────────────────────
   Uppercase mono with wide tracking. Used for field names, section headers,
   and any metadata. Deliberately small and quiet — it labels, never competes. */

export function MicroLabel({
  children,
  className,
  as: Tag = "span",
}: {
  children: React.ReactNode;
  className?: string;
  as?: "span" | "div" | "label" | "h2" | "h3";
}) {
  return (
    <Tag
      className={cn(
        "font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground",
        className
      )}
    >
      {children}
    </Tag>
  );
}

/* ── INDEX MARKER ───────────────────────────────────────────────────────────
   The numbered reference in the left gutter (01, 02, …). This is the element
   that makes a list read as a citation list rather than a feed. */

export function IndexMarker({
  n,
  active,
  className,
}: {
  n: number;
  active?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "tabular select-none font-mono text-[10px] leading-none",
        active ? "text-primary" : "text-muted-foreground/50",
        className
      )}
    >
      {String(n).padStart(2, "0")}
    </span>
  );
}

/* ── PAGE HEADER ────────────────────────────────────────────────────────────
   Eyebrow + title + one line of prose, then a rule. Every page opens the same
   way so navigating between them feels like turning a page, not switching apps. */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-8">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          {eyebrow && <MicroLabel className="mb-2 block">{eyebrow}</MicroLabel>}
          <h1 className="truncate text-[22px] font-medium leading-tight tracking-[-0.01em] text-foreground">
            {title}
          </h1>
          {description && (
            <p className="mt-1.5 max-w-xl text-[13px] leading-relaxed text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      <hr className="mt-6 border-border" />
    </header>
  );
}

/* ── FIELD ──────────────────────────────────────────────────────────────────
   A labelled form row. Hint sits under the control, not in a tooltip, because
   the choices here (engine, workspace) have real cost consequences. */

export function Field({
  label,
  hint,
  htmlFor,
  children,
  className,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <MicroLabel as="label" className="block" {...(htmlFor ? { htmlFor } : {})}>
        {label}
      </MicroLabel>
      {children}
      {hint && <p className="text-[12px] leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}

/* ── SEGMENTED CONTROL ──────────────────────────────────────────────────────
   Replaces radios and small tab bars. One inset track, active segment raised —
   reads as a physical switch, which suits binary choices like cloud/local. */

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "default",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; icon?: React.ElementType }[];
  className?: string;
  size?: "sm" | "default";
}) {
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md border border-border bg-muted/40 p-0.5",
        className
      )}
    >
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[5px] font-medium transition-colors",
              size === "sm" ? "px-2 py-1 text-[11px]" : "px-3 py-1.5 text-[12px]",
              active
                ? "bg-accent text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {Icon && <Icon className="h-3 w-3" />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

/* ── EMPTY STATE ────────────────────────────────────────────────────────────
   Dashed rule box, mono headline. No illustration: an empty research workspace
   is a normal state, not an error worth decorating. */

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: { label: string; to: string };
}) {
  return (
    <div className="rounded-md border border-dashed border-border px-6 py-14 text-center">
      <p className="font-mono text-[12px] uppercase tracking-[0.14em] text-muted-foreground">
        {title}
      </p>
      {description && (
        <p className="mx-auto mt-3 max-w-sm text-[13px] leading-relaxed text-muted-foreground/80">
          {description}
        </p>
      )}
      {action && (
        <Link
          to={action.to}
          className="mt-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-primary hover:underline"
        >
          {action.label}
          <span aria-hidden>→</span>
        </Link>
      )}
    </div>
  );
}

/* ── STAT ───────────────────────────────────────────────────────────────────
   Big tabular number over a mono label. Used in workspace headers and cards. */

export function Stat({
  value,
  label,
  accent,
}: {
  value: React.ReactNode;
  label: string;
  accent?: boolean;
}) {
  return (
    <div>
      <div
        className={cn(
          "tabular font-mono text-[18px] leading-none",
          accent ? "text-primary" : "text-foreground"
        )}
      >
        {value}
      </div>
      <MicroLabel className="mt-1.5 block">{label}</MicroLabel>
    </div>
  );
}

/* ── GUTTER LIST ────────────────────────────────────────────────────────────
   Rows in a numbered left gutter with a hairline connecting them. The shared
   container behind job history, claims, and themes so all three scan alike. */

export function GutterList({ children }: { children: React.ReactNode }) {
  return <div className="divide-y divide-border border-y border-border">{children}</div>;
}

export function GutterRow({
  n,
  children,
  onClick,
  className,
}: {
  n: number;
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const interactive = Boolean(onClick);
  return (
    <div
      {...(interactive
        ? { role: "button", tabIndex: 0, onClick, onKeyDown: onEnter(onClick!) }
        : {})}
      className={cn(
        "group flex gap-4 px-1 py-3 transition-colors",
        interactive && "cursor-pointer hover:bg-accent/40",
        className
      )}
    >
      <div className="w-6 shrink-0 pt-1 text-right">
        <IndexMarker n={n} />
      </div>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function onEnter(fn: () => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fn();
    }
  };
}

/* ── INLINE CODE / IDENTIFIER ───────────────────────────────────────────────
   For ids, workspace names, chunk refs — anything that is data, not prose. */

export function Mono({
  children,
  className,
  dim,
}: {
  children: React.ReactNode;
  className?: string;
  dim?: boolean;
}) {
  return (
    <span
      className={cn(
        "font-mono text-[11px]",
        dim ? "text-muted-foreground" : "text-foreground/80",
        className
      )}
    >
      {children}
    </span>
  );
}

/* ── SECTION ────────────────────────────────────────────────────────────────
   A labelled block with an optional right-side control. */

export function Section({
  label,
  aside,
  children,
  className,
}: {
  label: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <MicroLabel as="h2">{label}</MicroLabel>
        {aside}
      </div>
      {children}
    </section>
  );
}
