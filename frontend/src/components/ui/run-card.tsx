"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { WorkflowRun, WORKFLOW_LABELS } from "@/lib/types";
import { runs as runsApi } from "@/lib/api";
import { StatusBadge } from "./status-badge";
import { WorkflowIcon } from "./workflow-icon";
import { Calendar, FileStack, ArrowUpRight, Trash2, Loader2 } from "lucide-react";
import { BUSINESS_TZ } from "@/lib/utils";

interface RunCardProps {
  run: WorkflowRun;
  onDeleted?: () => void;
}

export function RunCard({ run, onDeleted }: RunCardProps) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  // run_date arrives as "YYYY-MM-DD". Render it as a fixed calendar date in
  // the business timezone (PST) so it cannot drift across viewer timezones.
  const date = new Date(`${run.run_date.slice(0, 10)}T12:00:00Z`).toLocaleDateString(
    "en-US",
    {
      timeZone: BUSINESS_TZ,
      month: "short",
      day: "numeric",
      year: "numeric",
    },
  );

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete "${run.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await runsApi.delete(run.id);
      onDeleted?.();
      router.refresh();
    } catch {
      setDeleting(false);
    }
  }

  return (
    <Link
      href={`/runs/${run.id}`}
      className="group relative flex flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className="flex items-start gap-3">
        <WorkflowIcon workflow={run.workflow_type} size="md" />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            {WORKFLOW_LABELS[run.workflow_type] ?? run.workflow_type}
          </p>
          <h3 className="mt-0.5 truncate text-sm font-semibold text-foreground">
            {run.name}
          </h3>
        </div>
        <ArrowUpRight className="size-4 shrink-0 text-muted-foreground opacity-0 transition-all duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:opacity-100 group-hover:text-primary" />
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Calendar className="size-3" aria-hidden />
            {date}
          </span>
          <span className="flex items-center gap-1">
            <FileStack className="size-3" aria-hidden />
            {run.file_count} {run.file_count === 1 ? "file" : "files"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          <button
            onClick={handleDelete}
            disabled={deleting}
            aria-label="Delete run"
            title="Delete run"
            className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 cursor-pointer"
          >
            {deleting
              ? <Loader2 className="size-3.5 animate-spin" />
              : <Trash2 className="size-3.5" />}
          </button>
        </div>
      </div>
    </Link>
  );
}
