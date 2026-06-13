"use client";

import { useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { runs as runsApi } from "@/lib/api";
import { WorkflowType, WORKFLOW_LABELS } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { WorkflowIcon } from "@/components/ui/workflow-icon";
import { ArrowLeft, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

const WORKFLOW_TYPES: WorkflowType[] = [
  "web_orders_check",
  "jetro_reconciliation",
  "vendor_bill_po_bank",
  "combined_price_changes",
];

const WORKFLOW_DESCRIPTIONS: Record<WorkflowType, string> = {
  web_orders_check: "Validate and enrich daily web orders; split same-day vs. future orders.",
  jetro_reconciliation: "Reconcile Restaurant Depot invoices against customer orders.",
  vendor_bill_po_bank: "Match vendor bill images to QuickBooks PO exports.",
  combined_price_changes: "Consolidate cost changes from Jetro and vendor bills.",
};

export default function NewRunPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [workflowType, setWorkflowType] = useState<WorkflowType>(
    (searchParams.get("type") as WorkflowType) ?? "web_orders_check"
  );
  const [name, setName] = useState("");
  const [runDate, setRunDate] = useState(new Date().toISOString().split("T")[0]);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const run = (await runsApi.create({
        workflow_type: workflowType,
        name: name || `${WORKFLOW_LABELS[workflowType]} — ${runDate}`,
        run_date: runDate,
        notes: notes || undefined,
      })) as { id: string };
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create run");
      setLoading(false);
    }
  }

  const inputCls = "w-full rounded-lg border border-input bg-card px-3 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30";

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-8">
      <div className="flex items-center gap-3">
        <Link
          href="/runs"
          className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Back to runs"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Create</p>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">New Run</h1>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Workflow type */}
        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Workflow
          </label>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {WORKFLOW_TYPES.map((wf) => {
              const selected = workflowType === wf;
              return (
                <button
                  key={wf}
                  type="button"
                  onClick={() => setWorkflowType(wf)}
                  aria-pressed={selected}
                  className={cn(
                    "group relative flex items-start gap-3 rounded-xl border p-4 text-left transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    selected
                      ? "border-primary bg-primary/[0.04] shadow-sm"
                      : "border-border bg-card hover:border-primary/40 hover:shadow-sm",
                  )}
                >
                  <WorkflowIcon workflow={wf} size="md" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground">{WORKFLOW_LABELS[wf]}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground leading-snug">
                      {WORKFLOW_DESCRIPTIONS[wf]}
                    </p>
                  </div>
                  {selected && (
                    <span className="absolute right-3 top-3 inline-flex size-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="size-3" strokeWidth={3} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Name */}
          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="name" className="text-xs font-medium text-foreground">
              Run Name <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`${WORKFLOW_LABELS[workflowType]} — ${runDate}`}
              className={inputCls}
            />
          </div>

          {/* Date */}
          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="run-date" className="text-xs font-medium text-foreground">
              Run Date
            </label>
            <input
              id="run-date"
              type="date"
              required
              value={runDate}
              onChange={(e) => setRunDate(e.target.value)}
              className={inputCls}
            />
          </div>

          {/* Notes */}
          <div className="space-y-1.5 sm:col-span-2">
            <label htmlFor="notes" className="text-xs font-medium text-foreground">
              Notes <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <textarea
              id="notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={cn(inputCls, "resize-none")}
            />
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex gap-3 pt-2">
          <Button type="submit" size="lg" disabled={loading}>
            {loading ? "Creating…" : "Create Run & Upload Files"}
          </Button>
          <Link href="/runs">
            <Button variant="outline" type="button" size="lg">
              Cancel
            </Button>
          </Link>
        </div>
      </form>
    </div>
  );
}
