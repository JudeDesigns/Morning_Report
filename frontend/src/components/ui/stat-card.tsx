import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: number | string;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger";
  loading?: boolean;
  className?: string;
}

const TONES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-primary bg-primary/10 ring-1 ring-inset ring-primary/15",
  success:
    "text-emerald-700 bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:text-emerald-300 dark:bg-emerald-950/40 dark:ring-emerald-900/60",
  warning:
    "text-amber-800 bg-amber-50 ring-1 ring-inset ring-amber-200 dark:text-amber-300 dark:bg-amber-950/40 dark:ring-amber-900/60",
  danger:
    "text-rose-700 bg-rose-50 ring-1 ring-inset ring-rose-200 dark:text-rose-300 dark:bg-rose-950/40 dark:ring-rose-900/60",
};

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  loading,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "group rounded-xl border border-border bg-card px-5 py-4 shadow-sm transition-all hover:shadow-md hover:border-primary/30",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground tabular-nums">
            {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-muted" /> : value}
          </p>
          {hint && (
            <p className="mt-1 text-xs text-muted-foreground line-clamp-1">{hint}</p>
          )}
        </div>
        {Icon && (
          <span
            className={cn(
              "inline-flex size-9 shrink-0 items-center justify-center rounded-lg transition-transform group-hover:scale-105",
              TONES[tone],
            )}
            aria-hidden
          >
            <Icon className="size-4" />
          </span>
        )}
      </div>
    </div>
  );
}
