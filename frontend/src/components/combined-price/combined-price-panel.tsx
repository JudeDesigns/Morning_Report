"use client";

import { useEffect, useState } from "react";
import { runs as runsApi, combinedPrice as cpApi } from "@/lib/api";
import { WorkflowRun } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Loader2, Play, Link2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface CombinedPricePanelProps {
  runId: string;
  disabled?: boolean;
  onProcessed?: () => void;
}

const SOURCE_STATUSES = new Set(["processed", "exported"]);

export function CombinedPricePanel({ runId, disabled, onProcessed }: CombinedPricePanelProps) {
  const [jetroRuns, setJetroRuns] = useState<WorkflowRun[]>([]);
  const [vendorRuns, setVendorRuns] = useState<WorkflowRun[]>([]);
  const [jetroId, setJetroId] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      runsApi.list({ workflow_type: "jetro_reconciliation", limit: 50 }),
      runsApi.list({ workflow_type: "vendor_bill_po_bank", limit: 50 }),
    ])
      .then(([j, v]) => {
        if (cancelled) return;
        setJetroRuns((j as WorkflowRun[]).filter((r) => SOURCE_STATUSES.has(r.status)));
        setVendorRuns((v as WorkflowRun[]).filter((r) => SOURCE_STATUSES.has(r.status)));
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load source runs"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleProcess() {
    if (!jetroId && !vendorId) {
      setError("Pick at least one source run (Jetro or Vendor Bill).");
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      await cpApi.process(runId, jetroId || undefined, vendorId || undefined);
      onProcessed?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
    } finally {
      setProcessing(false);
    }
  }

  const selectCls =
    "w-full rounded-lg border border-input bg-card px-3 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30";

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start gap-2.5">
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/[0.08] text-primary">
          <Link2 className="size-4" />
        </span>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold text-foreground">Source Runs</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Combine price changes from any processed Jetro reconciliation and/or vendor-bill run.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="jetro-source" className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Jetro Source Run
            </label>
            <select
              id="jetro-source"
              value={jetroId}
              onChange={(e) => setJetroId(e.target.value)}
              className={selectCls}
              disabled={disabled || processing}
            >
              <option value="">— None —</option>
              {jetroRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} · {new Date(r.run_date).toLocaleDateString()}
                </option>
              ))}
            </select>
            {jetroRuns.length === 0 && (
              <p className="text-[11px] text-muted-foreground">No processed Jetro runs available.</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="vendor-source" className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Vendor Bill Source Run
            </label>
            <select
              id="vendor-source"
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              className={selectCls}
              disabled={disabled || processing}
            >
              <option value="">— None —</option>
              {vendorRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} · {new Date(r.run_date).toLocaleDateString()}
                </option>
              ))}
            </select>
            {vendorRuns.length === 0 && (
              <p className="text-[11px] text-muted-foreground">No processed vendor-bill runs available.</p>
            )}
          </div>
        </div>
      )}

      {error && (
        <p className={cn("mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive")}>
          {error}
        </p>
      )}

      <div className="mt-4 flex justify-end">
        <Button onClick={handleProcess} disabled={disabled || processing || loading || (!jetroId && !vendorId)}>
          {processing ? (
            <><Loader2 className="size-3.5 animate-spin" />Processing…</>
          ) : (
            <><Play className="size-3.5" />Combine Price Changes</>
          )}
        </Button>
      </div>
    </section>
  );
}
