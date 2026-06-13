import { cn } from "@/lib/utils";
import { RunStatus, STATUS_LABELS } from "@/lib/types";

const STATUS_STYLES: Record<RunStatus, { wrap: string; dot: string }> = {
  draft: {
    wrap: "bg-muted text-muted-foreground ring-1 ring-inset ring-border",
    dot: "bg-muted-foreground/60",
  },
  files_uploaded: {
    wrap: "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-900/60",
    dot: "bg-sky-500",
  },
  extraction_pending: {
    wrap: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60",
    dot: "bg-amber-500",
  },
  extraction_review: {
    wrap: "bg-orange-50 text-orange-800 ring-1 ring-inset ring-orange-200 dark:bg-orange-950/40 dark:text-orange-300 dark:ring-orange-900/60",
    dot: "bg-orange-500",
  },
  ready_to_process: {
    wrap: "bg-violet-50 text-violet-800 ring-1 ring-inset ring-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:ring-violet-900/60",
    dot: "bg-violet-500",
  },
  processing: {
    wrap: "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-900/60",
    dot: "bg-sky-500 animate-pulse",
  },
  validation_failed: {
    wrap: "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:ring-rose-900/60",
    dot: "bg-rose-500",
  },
  processed: {
    wrap: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900/60",
    dot: "bg-emerald-500",
  },
  exported: {
    wrap: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900/60",
    dot: "bg-emerald-600",
  },
  archived: {
    wrap: "bg-muted text-muted-foreground ring-1 ring-inset ring-border",
    dot: "bg-muted-foreground/40",
  },
};

interface StatusBadgeProps {
  status: RunStatus;
  className?: string;
  showDot?: boolean;
}

export function StatusBadge({ status, className, showDot = true }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.draft;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium tracking-tight",
        style.wrap,
        className,
      )}
    >
      {showDot && <span className={cn("size-1.5 rounded-full", style.dot)} aria-hidden />}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
