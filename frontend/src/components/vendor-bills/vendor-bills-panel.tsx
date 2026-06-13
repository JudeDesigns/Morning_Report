"use client";

import { useCallback, useEffect, useState } from "react";
import { vendorBills as vbApi } from "@/lib/api";
import { UploadedFile, VendorBill } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { BillReviewDialog } from "@/components/vendor-bills/bill-review-dialog";
import { cn } from "@/lib/utils";
import {
  Loader2,
  Sparkles,
  FileSearch,
  CheckCircle2,
  AlertTriangle,
  PackageOpen,
  RefreshCw,
  TableProperties,
  FlagTriangleRight,
} from "lucide-react";

const BILL_FILE_TYPES = new Set(["vendor_bill_image", "vendor_bill_pdf"]);

interface PoBankStatus {
  total: number;
  vendors: number;
}

interface ImportRow {
  line: number;
  item_code: string | null;
  description: string | null;
  price: number | null;
  qty: number | null;
  total: number | null;
  ref: string | null;
  date: string | null;
  vendor: string | null;
  type: string | null;
  highlight_status: string | null;
}

interface VendorBillsPanelProps {
  runId: string;
  uploadedFiles: UploadedFile[];
  onChange?: () => void;
}

export function VendorBillsPanel({ runId, uploadedFiles, onChange }: VendorBillsPanelProps) {
  const [bills, setBills] = useState<VendorBill[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewBillId, setReviewBillId] = useState<string | null>(null);
  const [poStatus, setPoStatus] = useState<PoBankStatus | null>(null);
  const [importRows, setImportRows] = useState<ImportRow[]>([]);
  const [showPreview, setShowPreview] = useState(false);

  const refreshPoStatus = useCallback(async () => {
    try {
      const rows = (await vbApi.poBank(runId)) as Array<{ vendor?: string }>;
      if (rows.length > 0) {
        const vendors = new Set(rows.map((r) => r.vendor).filter(Boolean)).size;
        setPoStatus({ total: rows.length, vendors });
      }
    } catch {
      // silently ignore — PO bank just hasn't been loaded yet
    }
  }, [runId]);

  const refreshImportRows = useCallback(async () => {
    try {
      const rows = (await vbApi.importRows(runId)) as ImportRow[];
      setImportRows(rows);
    } catch {
      // no rows yet — normal before any bill is processed
    }
  }, [runId]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const list = (await vbApi.bills(runId)) as VendorBill[];
      setBills(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load bills");
    } finally {
      setLoading(false);
    }
    await refreshImportRows();
  }, [runId, refreshImportRows]);

  useEffect(() => {
    refresh();
    refreshPoStatus();
  }, [refresh, refreshPoStatus]);

  const billFiles = uploadedFiles.filter((f) => BILL_FILE_TYPES.has(f.file_type));
  const extractedFileIds = new Set(bills.map((b) => b.source_file_id).filter(Boolean));
  const pendingExtraction = billFiles.filter((f) => !extractedFileIds.has(f.id));

  async function handleLoadPo() {
    setBusyId("po");
    setError(null);
    try {
      const result = (await vbApi.loadPo(runId)) as { product_lines?: number };
      await refreshPoStatus();
      onChange?.();
      // If the result includes product_lines, update status immediately from the response
      if (result?.product_lines !== undefined) {
        // refreshPoStatus already updated it, but this is a fallback
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load PO bank");
    } finally {
      setBusyId(null);
    }
  }

  async function handleExtract(fileId: string) {
    setBusyId(fileId);
    setError(null);
    try {
      await vbApi.extractBill(runId, fileId);
      await refresh();
      onChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleProcess(billId: string) {
    setBusyId(billId);
    setError(null);
    try {
      await vbApi.processBill(runId, billId);
      await refresh();
      onChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleFinalize() {
    setBusyId("finalize");
    setError(null);
    try {
      await vbApi.finalize(runId);
      onChange?.(); // triggers page refresh → canExport becomes true → Download Workbook appears
    } catch (e) {
      setError(e instanceof Error ? e.message : "Finalize failed");
    } finally {
      setBusyId(null);
    }
  }

  const matchedBillCount = bills.filter((b) => b.extraction_status === "processed").length;

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Vendor Bill Pipeline</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Load the PO Bank once, then extract and process each bill as images arrive throughout the day.{" "}
            <span className="font-medium text-foreground/70">Export only when all bills are uploaded.</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {matchedBillCount > 0 && (
            <Button
              size="sm"
              onClick={handleFinalize}
              disabled={busyId === "finalize"}
              title="Done adding bills for today? Click to unlock the Download Workbook button. You can always reopen the run after export to add more."
            >
              {busyId === "finalize" ? (
                <><Loader2 className="size-3.5 animate-spin" />Finalizing…</>
              ) : (
                <><FlagTriangleRight className="size-3.5" />Done — Ready to Export</>
              )}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleLoadPo} disabled={busyId === "po"}>
            {busyId === "po" ? (
              <><Loader2 className="size-3.5 animate-spin" />Loading…</>
            ) : poStatus ? (
              <><RefreshCw className="size-3.5" />Reload PO Bank</>
            ) : (
              <><PackageOpen className="size-3.5" />Load PO Bank</>
            )}
          </Button>
        </div>
      </div>

      {/* PO Bank status */}
      {poStatus ? (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/50 px-3 py-2 dark:border-emerald-900/50 dark:bg-emerald-950/20">
          <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <p className="text-xs text-emerald-700 dark:text-emerald-300">
            PO Bank loaded — <span className="font-semibold">{poStatus.total} POs</span> from{" "}
            <span className="font-semibold">{poStatus.vendors} vendors</span>
          </p>
        </div>
      ) : (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2 dark:border-amber-900/50 dark:bg-amber-950/20">
          <AlertTriangle className="size-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-xs text-amber-700 dark:text-amber-300">
            PO Bank not loaded yet — upload the QuickBooks PO export and click <span className="font-semibold">Load PO Bank</span> first.
          </p>
        </div>
      )}

      {error && (
        <p className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {pendingExtraction.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Awaiting AI Extraction ({pendingExtraction.length})
          </p>
          <ul className="space-y-1.5">
            {pendingExtraction.map((f) => (
              <li
                key={f.id}
                className="flex items-center gap-3 rounded-lg border border-dashed border-border bg-muted/20 px-3 py-2"
              >
                <FileSearch className="size-4 shrink-0 text-muted-foreground" />
                <p className="min-w-0 flex-1 truncate text-sm">{f.original_filename}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleExtract(f.id)}
                  disabled={busyId === f.id}
                >
                  {busyId === f.id ? (
                    <><Loader2 className="size-3.5 animate-spin" />Extracting…</>
                  ) : (
                    <><Sparkles className="size-3.5" />Extract with Claude</>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        </div>
      ) : bills.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-muted/20 py-8 text-center text-xs text-muted-foreground">
          No extracted bills yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {bills.map((b) => (
            <BillRow
              key={b.id}
              bill={b}
              busy={busyId === b.id}
              onReview={() => setReviewBillId(b.id)}
              onProcess={() => handleProcess(b.id)}
            />
          ))}
        </ul>
      )}

      {/* Bill Import Preview */}
      {importRows.length > 0 && (
        <div className="mt-4 border-t border-border pt-4">
          <button
            className="mb-3 flex w-full items-center gap-2 text-left"
            onClick={() => setShowPreview((v) => !v)}
          >
            <TableProperties className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Bill Import Preview ({importRows.length} rows)
            </span>
            <span className="ml-auto text-[10px] text-muted-foreground">
              {showPreview ? "▲ Hide" : "▼ Show"}
            </span>
          </button>
          {showPreview && (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    {["#", "Item Code", "Description", "Vendor", "Ref", "Date", "Qty", "Price", "Total", "Status"].map((h) => (
                      <th key={h} className="px-2 py-1.5 text-left font-semibold text-muted-foreground whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {importRows.map((row) => {
                    const isNotOnPo = row.highlight_status === "not_on_po" || row.highlight_status === "missing_po_item";
                    return (
                      <tr
                        key={row.line}
                        className={cn(
                          "border-b border-border/50 last:border-0",
                          isNotOnPo
                            ? "bg-red-50/60 dark:bg-red-950/20"
                            : "bg-card hover:bg-muted/30",
                        )}
                      >
                        <td className="px-2 py-1.5 text-muted-foreground">{row.line}</td>
                        <td className="px-2 py-1.5 font-mono">{row.item_code ?? <span className="text-destructive">—</span>}</td>
                        <td className="max-w-[200px] truncate px-2 py-1.5" title={row.description ?? ""}>{row.description}</td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{row.vendor}</td>
                        <td className="px-2 py-1.5 font-mono">{row.ref}</td>
                        <td className="px-2 py-1.5 whitespace-nowrap">{row.date}</td>
                        <td className="px-2 py-1.5 text-right">{row.qty}</td>
                        <td className="px-2 py-1.5 text-right">${row.price?.toFixed(2)}</td>
                        <td className="px-2 py-1.5 text-right font-medium">${row.total?.toFixed(2)}</td>
                        <td className="px-2 py-1.5">
                          {isNotOnPo ? (
                            <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:bg-red-900/40 dark:text-red-300">
                              Not on PO
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                              Matched
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {reviewBillId && (
        <BillReviewDialog
          runId={runId}
          billId={reviewBillId}
          open={!!reviewBillId}
          onOpenChange={(o) => !o && setReviewBillId(null)}
          onSaved={() => {
            refresh();
            onChange?.();
          }}
        />
      )}
    </section>
  );
}

function BillRow({
  bill,
  busy,
  onReview,
  onProcess,
}: {
  bill: VendorBill;
  busy: boolean;
  onReview: () => void;
  onProcess: () => void;
}) {
  const status = bill.extraction_status ?? "review";
  const needsReview =
    status === "review" || (bill.header_needs_review && bill.header_needs_review.length > 0);
  const isProcessed = status === "processed";

  return (
    <li
      className={cn(
        "flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors",
        isProcessed
          ? "border-emerald-200 bg-emerald-50/40 dark:border-emerald-900/60 dark:bg-emerald-950/20"
          : needsReview
          ? "border-amber-200 bg-amber-50/40 dark:border-amber-900/60 dark:bg-amber-950/20"
          : "border-border",
      )}
    >
      <span
        className={cn(
          "inline-flex size-8 shrink-0 items-center justify-center rounded-lg",
          isProcessed
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
            : needsReview
            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
            : "bg-muted text-muted-foreground",
        )}
      >
        {isProcessed ? (
          <CheckCircle2 className="size-4" />
        ) : needsReview ? (
          <AlertTriangle className="size-4" />
        ) : (
          <FileSearch className="size-4" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="truncate text-sm font-medium text-foreground">
            {bill.vendor_confirmed ?? bill.vendor_extracted ?? "Unknown vendor"}
          </p>
          {bill.invoice_number && (
            <span className="font-mono text-[11px] text-muted-foreground">
              #{bill.invoice_number}
            </span>
          )}
          {typeof bill.header_confidence === "number" && (
            <ConfidenceBadge value={bill.header_confidence} needsReview={needsReview} />
          )}
        </div>
        <p className="mt-0.5 text-[11px] text-muted-foreground capitalize">
          {bill.bill_type} · {status}
          {bill.header_needs_review && bill.header_needs_review.length > 0 && (
            <> · review: {bill.header_needs_review.join(", ")}</>
          )}
        </p>
      </div>
      <div className="flex gap-1.5 shrink-0">
        {!isProcessed && (
          <Button variant="outline" size="sm" onClick={onReview}>
            Review
          </Button>
        )}
        {!isProcessed && (
          <Button
            size="sm"
            onClick={onProcess}
            disabled={busy}
            title="Match this bill's lines against the PO Bank. You can keep uploading more bills after this."
          >
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : "Match to POs"}
          </Button>
        )}
      </div>
    </li>
  );
}
