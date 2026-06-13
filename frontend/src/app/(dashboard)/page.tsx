"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { runs as runsApi } from "@/lib/api";
import {
  WorkflowRun,
  WORKFLOW_LABELS,
  WorkflowType,
} from "@/lib/types";
import { RunCard } from "@/components/ui/run-card";
import { StatCard } from "@/components/ui/stat-card";
import { WorkflowIcon } from "@/components/ui/workflow-icon";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth-context";
import {
  Plus,
  Loader2,
  Activity,
  CheckCircle2,
  Layers,
  AlertCircle,
  ArrowRight,
} from "lucide-react";

const WORKFLOW_TYPES: WorkflowType[] = [
  "web_orders_check",
  "jetro_reconciliation",
  "vendor_bill_po_bank",
  "combined_price_changes",
];

const WORKFLOW_DESC: Record<WorkflowType, string> = {
  web_orders_check: "Validate & enrich daily customer orders",
  jetro_reconciliation: "Match RD invoices to customer orders",
  vendor_bill_po_bank: "Pair vendor bills with QuickBooks POs",
  combined_price_changes: "Consolidate price changes across sources",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [allRuns, setAllRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    runsApi
      .list({ limit: 20 })
      .then((r) => setAllRuns(r as WorkflowRun[]))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const recent = allRuns.slice(0, 6);

  const stats = {
    total: allRuns.length,
    active: allRuns.filter((r) =>
      ["processing", "ready_to_process", "extraction_review", "files_uploaded"].includes(r.status),
    ).length,
    processed: allRuns.filter((r) => ["processed", "exported"].includes(r.status)).length,
    needsAttention: allRuns.filter((r) =>
      ["validation_failed", "extraction_review"].includes(r.status),
    ).length,
  };

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 18) return "Good afternoon";
    return "Good evening";
  })();
  const firstName = user?.name?.split(" ")[0] ?? "";

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6 lg:p-8">
      {/* Header */}
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Dashboard</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            {greeting}{firstName ? `, ${firstName}` : ""}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Here&rsquo;s the morning report for {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}.
          </p>
        </div>
        <Link href="/runs/new">
          <Button size="lg">
            <Plus className="size-3.5" />
            New Run
          </Button>
        </Link>
      </header>

      {/* Stats */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Runs" value={stats.total} icon={Layers} loading={loading} />
        <StatCard label="Active" value={stats.active} icon={Activity} tone="default" loading={loading} hint="In progress or pending review" />
        <StatCard label="Processed" value={stats.processed} icon={CheckCircle2} tone="success" loading={loading} />
        <StatCard label="Needs Attention" value={stats.needsAttention} icon={AlertCircle} tone={stats.needsAttention > 0 ? "warning" : "default"} loading={loading} />
      </section>

      {/* Workflow shortcuts */}
      <section>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Start a Workflow</h2>
            <p className="text-xs text-muted-foreground mt-0.5">Choose a process to kick off a new run.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {WORKFLOW_TYPES.map((wf) => (
            <Link
              key={wf}
              href={`/runs/new?type=${wf}`}
              className="group flex items-center gap-4 rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <WorkflowIcon workflow={wf} size="lg" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-foreground">
                  {WORKFLOW_LABELS[wf]}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">
                  {WORKFLOW_DESC[wf]}
                </p>
              </div>
              <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-primary" />
            </Link>
          ))}
        </div>
      </section>

      {/* Recent runs */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Recent Runs</h2>
          <Link href="/runs" className="text-xs font-medium text-primary hover:underline">
            View all →
          </Link>
        </div>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        )}
        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </p>
        )}
        {!loading && !error && recent.length === 0 && (
          <div className="rounded-xl border border-dashed border-border bg-card/50 py-14 text-center">
            <p className="text-sm text-muted-foreground">No runs yet.</p>
            <Link href="/runs/new" className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
              Create your first run →
            </Link>
          </div>
        )}
        {!loading && !error && recent.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((run) => (
              <RunCard key={run.id} run={run} onDeleted={() => setRefreshKey((k) => k + 1)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
