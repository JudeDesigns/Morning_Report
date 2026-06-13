import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

interface ConfidenceBadgeProps {
  value: number | undefined;
  /** Higher than this is "high"; lower than `low` is "low"; otherwise "medium". */
  high?: number;
  low?: number;
  needsReview?: boolean;
  className?: string;
  showValue?: boolean;
}

/** Renders a per-field extraction confidence indicator (0–1 scale). */
export function ConfidenceBadge({
  value,
  high = 0.9,
  low = 0.7,
  needsReview,
  className,
  showValue = true,
}: ConfidenceBadgeProps) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const tier: "high" | "medium" | "low" = needsReview
    ? "low"
    : value >= high
    ? "high"
    : value >= low
    ? "medium"
    : "low";

  const tone = {
    high: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900/60",
    medium: "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60",
    low: "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:ring-rose-900/60",
  }[tier];

  const Icon = tier === "high" ? CheckCircle2 : tier === "medium" ? Info : AlertCircle;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums ring-1 ring-inset",
        tone,
        className,
      )}
      title={`Extraction confidence: ${pct}%${needsReview ? " — flagged for review" : ""}`}
    >
      <Icon className="size-2.5" aria-hidden />
      {showValue && <span>{pct}%</span>}
    </span>
  );
}
