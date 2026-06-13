"use client";

import { useState, FormEvent } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { AlertTriangle, X, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { runs as runsApi } from "@/lib/api";

interface OverrideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runId: string;
  check: string;
  title?: string;
  message: string;
  affectedInvoices?: (string | number)[];
  onSuccess?: () => void;
}

export function OverrideDialog({
  open,
  onOpenChange,
  runId,
  check,
  title = "Authorized Override Required",
  message,
  affectedInvoices,
  onSuccess,
}: OverrideDialogProps) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (reason.trim().length < 5) {
      setError("Reason must be at least 5 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await runsApi.override(runId, {
        check,
        reason: reason.trim(),
        affected_rows: affectedInvoices?.map(String),
      });
      setReason("");
      onOpenChange(false);
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Override failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 transition-opacity duration-200" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 w-[min(440px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border bg-card shadow-2xl outline-none data-[starting-style]:scale-95 data-[starting-style]:opacity-0 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 transition-all duration-200">
          <div className="flex items-start gap-3 border-b border-border px-5 py-4">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60">
              <AlertTriangle className="size-4" />
            </span>
            <div className="flex-1 min-w-0">
              <Dialog.Title className="text-sm font-semibold text-foreground">
                {title}
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                This action is logged and audit-trailed to your account.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close"
            >
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
            <p className="text-sm text-foreground/90 leading-relaxed">{message}</p>

            {affectedInvoices && affectedInvoices.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 dark:border-amber-900/60 dark:bg-amber-950/30">
                <p className="text-[11px] font-medium uppercase tracking-wider text-amber-800 dark:text-amber-300">
                  Affected invoices
                </p>
                <p className="mt-1 font-mono text-xs text-amber-900 dark:text-amber-200 break-all">
                  {affectedInvoices.join(", ")}
                </p>
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="override-reason" className="text-xs font-medium text-foreground">
                Override reason <span className="text-muted-foreground">(min. 5 chars)</span>
              </label>
              <textarea
                id="override-reason"
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Manual recount confirmed, discrepancy reconciled offline"
                className="w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
              />
            </div>

            {error && (
              <p className="text-xs text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <Dialog.Close render={<Button variant="outline" type="button" />}>
                Cancel
              </Dialog.Close>
              <Button type="submit" disabled={loading || reason.trim().length < 5}>
                <ShieldCheck className="size-3.5" />
                {loading ? "Recording…" : "Authorize Override"}
              </Button>
            </div>
          </form>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
