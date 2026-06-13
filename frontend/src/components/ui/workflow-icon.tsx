import {
  ShoppingCart,
  ClipboardList,
  Receipt,
  TrendingUp,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { WorkflowType } from "@/lib/types";

const WORKFLOW_ICONS: Record<WorkflowType, LucideIcon> = {
  web_orders_check: ShoppingCart,
  jetro_reconciliation: ClipboardList,
  vendor_bill_po_bank: Receipt,
  combined_price_changes: TrendingUp,
};

const WORKFLOW_TONES: Record<WorkflowType, string> = {
  web_orders_check:
    "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200 dark:bg-sky-950/30 dark:text-sky-300 dark:ring-sky-900/50",
  jetro_reconciliation:
    "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200 dark:bg-violet-950/30 dark:text-violet-300 dark:ring-violet-900/50",
  vendor_bill_po_bank:
    "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:ring-emerald-900/50",
  combined_price_changes:
    "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:ring-amber-900/50",
};

interface WorkflowIconProps {
  workflow: WorkflowType;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function WorkflowIcon({ workflow, size = "md", className }: WorkflowIconProps) {
  const Icon = WORKFLOW_ICONS[workflow] ?? Workflow;
  const tone = WORKFLOW_TONES[workflow] ?? "bg-muted text-muted-foreground";
  const dim =
    size === "sm" ? "size-7" : size === "lg" ? "size-11" : "size-9";
  const iconDim =
    size === "sm" ? "size-3.5" : size === "lg" ? "size-5" : "size-4";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-lg",
        dim,
        tone,
        className,
      )}
    >
      <Icon className={iconDim} />
    </span>
  );
}

export { WORKFLOW_TONES };
