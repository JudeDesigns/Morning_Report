"use client";

import { Dialog } from "@base-ui/react/dialog";
import { Download, X, FileSearch, ListChecks, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ExportConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pendingExtractions: number;
  pendingProcessing: number;
  totalBills: number;
  onConfirm: () => void;
  loading?: boolean;
}

export function ExportConfirmDialog({
  open,
  onOpenChange,
  pendingExtractions,
  pendingProcessing,
  totalBills,
  onConfirm,
  loading,
}: ExportConfirmDialogProps) {
  const hasPending = pendingExtractions > 0 || pendingProcessing > 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 transition-opacity duration-200" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 w-[min(460px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border bg-card shadow-2xl outline-none data-[starting-style]:scale-95 data-[starting-style]:opacity-0 data-[ending-style]:scale-95 data-[ending-style]:opacity-0 transition-all duration-200">
          <div className="flex items-start gap-3 border-b border-border px-5 py-4">
            <span
              className={
                hasPending
                  ? "inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60"
                  : "inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900/60"
              }
            >
              {hasPending ? <ListChecks className="size-4" /> : <CheckCircle2 className="size-4" />}
            </span>
            <div className="flex-1 min-w-0">
              <Dialog.Title className="text-sm font-semibold text-foreground">
                Ready to export?
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                {hasPending
                  ? "Some uploaded bills are not yet included in the workbook."
                  : `All ${totalBills} bill${totalBills === 1 ? "" : "s"} have been processed.`}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close"
            >
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <div className="space-y-4 px-5 py-4">
            {hasPending ? (
              <ul className="space-y-2">
                {pendingExtractions > 0 && (
                  <li className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 dark:border-amber-900/60 dark:bg-amber-950/30">
                    <FileSearch className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-300" />
                    <div className="text-xs text-amber-900 dark:text-amber-200">
                      <p className="font-medium">
                        {pendingExtractions} file{pendingExtractions === 1 ? "" : "s"} awaiting AI extraction
                      </p>
                      <p className="mt-0.5 text-amber-800/80 dark:text-amber-300/80">
                        These uploads have not been run through Claude yet.
                      </p>
                    </div>
                  </li>
                )}
                {pendingProcessing > 0 && (
                  <li className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 dark:border-amber-900/60 dark:bg-amber-950/30">
                    <ListChecks className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-300" />
                    <div className="text-xs text-amber-900 dark:text-amber-200">
                      <p className="font-medium">
                        {pendingProcessing} bill{pendingProcessing === 1 ? "" : "s"} awaiting review &amp; processing
                      </p>
                      <p className="mt-0.5 text-amber-800/80 dark:text-amber-300/80">
                        Extracted but not yet matched against the PO Bank.
                      </p>
                    </div>
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-sm text-foreground/90 leading-relaxed">
                After exporting, any remaining unmatched POs for vendors with confirmed
                bills will be listed as &ldquo;PO ordered but not billed&rdquo; in the workbook.
              </p>
            )}

            <p className="text-xs text-muted-foreground leading-relaxed">
              If more bills arrive later, an admin can <span className="font-medium text-foreground">Reopen Run</span> to continue.
            </p>

            <div className="flex justify-end gap-2 pt-1">
              <Dialog.Close render={<Button variant="outline" type="button" />}>
                Cancel
              </Dialog.Close>
              <Button type="button" onClick={onConfirm} disabled={loading}>
                <Download className="size-3.5" />
                {loading ? "Preparing…" : hasPending ? "Export anyway" : "Export workbook"}
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
