import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-emerald-700 text-white hover:bg-emerald-800 focus-visible:outline-emerald-700",
  secondary: "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50 focus-visible:outline-slate-500",
  ghost: "text-slate-700 hover:bg-slate-100 focus-visible:outline-slate-500",
  danger: "bg-red-700 text-white hover:bg-red-800 focus-visible:outline-red-700",
};

export function Button({
  variant = "primary",
  className,
  busy,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium",
        "focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
        VARIANTS[variant],
        className,
      )}
    >
      {busy ? "Working…" : children}
    </button>
  );
}

export function Field({
  label,
  hint,
  error,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string; id: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-800">
        {label}
      </label>
      <input
        id={id}
        {...props}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint || error ? `${id}-help` : undefined}
        className="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/30"
      />
      {(hint || error) && (
        <p id={`${id}-help`} className={cx("text-xs", error ? "text-red-700" : "text-slate-500")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-lg border border-slate-200 bg-white p-5 shadow-sm", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES = {
  neutral: "bg-slate-100 text-slate-700",
  good: "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200",
  warn: "bg-amber-50 text-amber-900 ring-1 ring-amber-200",
  bad: "bg-red-50 text-red-800 ring-1 ring-red-200",
  info: "bg-sky-50 text-sky-900 ring-1 ring-sky-200",
} as const;

export function Badge({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", TONES[tone])}>{children}</span>;
}

export function Alert({ tone = "info", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={cx("rounded-md px-4 py-3 text-sm", TONES[tone])}>
      {children}
    </div>
  );
}

export function statusTone(status: string): keyof typeof TONES {
  if (["ready", "verified", "confirmed", "paid", "resolved", "closed"].includes(status)) return "good";
  if (["rejected", "failed", "infected", "void"].includes(status)) return "bad";
  if (["needs_review", "needs_expert", "pending", "processing", "uploaded"].includes(status)) return "warn";
  return "neutral";
}

export function label(status: string): string {
  return status.replaceAll("_", " ");
}
