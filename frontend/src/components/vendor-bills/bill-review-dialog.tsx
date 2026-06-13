"use client";

import { useEffect, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { X, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfidenceBadge } from "@/components/ui/confidence-badge";
import { vendorBills as vbApi } from "@/lib/api";
import { VendorBill, VendorBillLine, PoRow } from "@/lib/types";
import { cn } from "@/lib/utils";

interface BillReviewDialogProps {
  runId: string;
  billId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
}

type LineDraft = VendorBillLine & { _dirty?: boolean };

export function BillReviewDialog({ runId, billId, open, onOpenChange, onSaved }: BillReviewDialogProps) {
  const [bill, setBill] = useState<VendorBill | null>(null);
  const [lines, setLines] = useState<LineDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availablePos, setAvailablePos] = useState<PoRow[]>([]);

  // Header drafts
  const [vendor, setVendor] = useState("");
  const [invoiceNo, setInvoiceNo] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    Promise.all([vbApi.bills(runId), vbApi.billLines(runId, billId), vbApi.poBank(runId)])
      .then(([allBills, billLines, poRows]) => {
        const b = (allBills as VendorBill[]).find((x) => x.id === billId) ?? null;
        setBill(b);
        setVendor(b?.vendor_confirmed ?? b?.vendor_extracted ?? "");
        setInvoiceNo(b?.invoice_number ?? "");
        setInvoiceDate(b?.invoice_date ?? "");
        setLines(billLines as LineDraft[]);
        // Keep all rows so already-matched POs (status "processed") are visible in the dropdown
        setAvailablePos(poRows as PoRow[]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load bill"))
      .finally(() => setLoading(false));
  }, [open, runId, billId]);

  function patchLine(idx: number, patch: Partial<VendorBillLine>) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch, _dirty: true } : l)));
  }

  function toggleConfirm(idx: number) {
    setLines((prev) =>
      prev.map((l, i) =>
        i === idx ? { ...l, user_confirmed: !l.user_confirmed, _dirty: true } : l,
      ),
    );
  }

  async function handleSave() {
    if (!bill) return;
    setSaving(true);
    setError(null);
    try {
      // Header
      await vbApi.confirmBill(runId, billId, {
        vendor_confirmed: vendor || undefined,
        invoice_number: invoiceNo || undefined,
        invoice_date: invoiceDate || undefined,
      });
      // Dirty lines
      const dirty = lines.filter((l) => l._dirty);
      for (const l of dirty) {
        await vbApi.updateLine(runId, billId, l.id, {
          bill_item_code: l.bill_item_code,
          description: l.description,
          qty: l.qty,
          rate: l.rate,
          total: l.total,
          user_confirmed: l.user_confirmed,
          forced_po_id: l.forced_po_id ?? null,
        });
      }
      onSaved?.();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const headerReview = new Set(bill?.header_needs_review ?? []);
  const confirmedCount = lines.filter((l) => l.user_confirmed).length;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-foreground/30 backdrop-blur-sm data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 transition-opacity duration-200" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 flex w-[min(960px,calc(100vw-2rem))] max-h-[90vh] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-border bg-card shadow-2xl outline-none">
          <div className="flex items-start gap-3 border-b border-border px-5 py-4">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/[0.08] text-primary">
              <Sparkles className="size-4" />
            </span>
            <div className="flex-1 min-w-0">
              <Dialog.Title className="text-sm font-semibold text-foreground">
                Review Extracted Bill
              </Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                Verify the fields flagged for review, then confirm each line before processing.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Close"
            >
              <X className="size-4" />
            </Dialog.Close>
          </div>

          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="size-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="overflow-y-auto px-5 py-4 space-y-5">
              {/* Header fields */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <HeaderField
                  label="Vendor"
                  value={vendor}
                  onChange={setVendor}
                  flagged={headerReview.has("vendor")}
                />
                <HeaderField
                  label="Invoice #"
                  value={invoiceNo}
                  onChange={setInvoiceNo}
                  flagged={headerReview.has("invoice_number")}
                />
                <HeaderField
                  label="Invoice Date"
                  type="date"
                  value={invoiceDate}
                  onChange={setInvoiceDate}
                  flagged={headerReview.has("invoice_date")}
                />
              </div>

              {/* Line items */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Line Items ({confirmedCount} / {lines.length} confirmed)
                  </p>
                  {confirmedCount < lines.length && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setLines((prev) => prev.map((l) => ({ ...l, user_confirmed: true, _dirty: true })))
                      }
                    >
                      Confirm All
                    </Button>
                  )}
                </div>
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/50 text-[10px] uppercase tracking-wider text-muted-foreground">
                      <tr>
                        <th className="px-2 py-2 text-left font-medium">Code</th>
                        <th className="px-2 py-2 text-left font-medium">Description</th>
                        <th className="px-2 py-2 text-right font-medium">Qty</th>
                        <th className="px-2 py-2 text-right font-medium">Rate</th>
                        <th className="px-2 py-2 text-right font-medium">Total</th>
                        <th className="px-2 py-2 text-left font-medium min-w-[180px]">PO Match</th>
                        <th className="px-2 py-2 text-center font-medium">OK</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map((l, i) => (
                        <LineRow key={l.id} line={l} availablePos={availablePos} onChange={(p) => patchLine(i, p)} onToggle={() => toggleConfirm(i)} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {error && (
                <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {error}
                </p>
              )}
            </div>
          )}

          <div className="flex items-center justify-between gap-2 border-t border-border px-5 py-3">
            <p className="text-[11px] text-muted-foreground">
              Confirmed lines will be used for PO matching when you process this bill.
            </p>
            <div className="flex gap-2">
              <Dialog.Close render={<Button variant="outline" type="button" />}>Cancel</Dialog.Close>
              <Button onClick={handleSave} disabled={saving || loading}>
                {saving ? <><Loader2 className="size-3.5 animate-spin" />Saving…</> : "Save & Close"}
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function HeaderField({
  label,
  value,
  onChange,
  flagged,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  flagged?: boolean;
  type?: "text" | "date";
}) {
  return (
    <div className="space-y-1">
      <label className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
        {flagged && (
          <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
            review
          </span>
        )}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "w-full rounded-lg border bg-background px-2.5 py-1.5 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30",
          flagged ? "border-amber-300 dark:border-amber-900/60" : "border-input",
        )}
      />
    </div>
  );
}

function LineRow({
  line,
  availablePos,
  onChange,
  onToggle,
}: {
  line: LineDraft;
  availablePos: PoRow[];
  onChange: (p: Partial<VendorBillLine>) => void;
  onToggle: () => void;
}) {
  const reviewSet = new Set(line.field_needs_review ?? []);
  const cellCls = (field: string) =>
    cn(
      "w-full bg-transparent px-1.5 py-1 text-xs outline-none rounded transition-colors focus:bg-background focus:ring-1 focus:ring-ring/40",
      reviewSet.has(field) && "ring-1 ring-amber-300 dark:ring-amber-900/60",
    );

  const forced = line.forced_po_id;
  // Effective selection: manual override > auto match result > nothing
  const effectiveId = forced ?? line.matched_po_id ?? null;
  const isNotOnPo = forced === "NOT_ON_PO" || (!forced && line.match_status === "not_on_po");
  const isMatched = effectiveId && effectiveId !== "NOT_ON_PO";

  return (
    <tr
      className={cn(
        "border-t border-border transition-colors",
        line.user_confirmed
          ? "bg-emerald-50/40 dark:bg-emerald-950/10"
          : "hover:bg-muted/30",
      )}
    >
      <td className="px-1 py-1">
        <input
          value={line.bill_item_code ?? ""}
          onChange={(e) => onChange({ bill_item_code: e.target.value })}
          className={cellCls("bill_item_code")}
        />
      </td>
      <td className="px-1 py-1">
        <div className="flex items-center gap-1.5">
          <input
            value={line.description ?? ""}
            onChange={(e) => onChange({ description: e.target.value })}
            className={cellCls("description")}
          />
          {typeof line.confidence === "number" && (
            <ConfidenceBadge value={line.confidence} needsReview={!!line.field_needs_review?.length} showValue={false} />
          )}
        </div>
      </td>
      <td className="px-1 py-1 text-right">
        <input
          type="number"
          step="0.01"
          value={line.qty ?? ""}
          onChange={(e) => onChange({ qty: e.target.value === "" ? undefined : Number(e.target.value) })}
          className={cn(cellCls("qty"), "text-right tabular-nums")}
        />
      </td>
      <td className="px-1 py-1 text-right">
        <input
          type="number"
          step="0.0001"
          value={line.rate ?? ""}
          onChange={(e) => onChange({ rate: e.target.value === "" ? undefined : Number(e.target.value) })}
          className={cn(cellCls("rate"), "text-right tabular-nums")}
        />
      </td>
      <td className="px-1 py-1 text-right">
        <input
          type="number"
          step="0.01"
          value={line.total ?? ""}
          onChange={(e) => onChange({ total: e.target.value === "" ? undefined : Number(e.target.value) })}
          className={cn(cellCls("total"), "text-right tabular-nums")}
        />
      </td>
      {/* PO Match selector */}
      <td className="px-1 py-1 min-w-[200px]">
        <select
          value={forced ?? (line.match_status === "not_on_po" ? "NOT_ON_PO" : (line.matched_po_id ?? ""))}
          onChange={(e) => {
            // If user picked the auto-matched PO explicitly, store it as forced so it's visible
            onChange({ forced_po_id: e.target.value === "" ? null : e.target.value });
          }}
          title="Override the auto-match, or mark as Not on PO"
          className={cn(
            "w-full rounded border px-1.5 py-1 text-xs outline-none transition-colors focus:ring-1 focus:ring-ring/40 bg-background",
            isMatched
              ? "border-emerald-400 text-emerald-700 dark:text-emerald-300"
              : isNotOnPo
              ? "border-rose-400 text-rose-700 dark:text-rose-300"
              : "border-amber-300 text-amber-700 dark:text-amber-300",
          )}
        >
          <option value="">— let engine decide —</option>
          <option value="NOT_ON_PO">🔴 Not on PO</option>
          {/* Available (unprocessed) POs */}
          {availablePos.filter((p) => p.status === "unprocessed").length > 0 && (
            <optgroup label="Available POs">
              {availablePos
                .filter((p) => p.status === "unprocessed")
                .map((po) => (
                  <option key={po.id} value={po.id}>
                    {po.item_code ? `[${po.item_code}] ` : ""}{(po.description ?? po.id).slice(0, 60)}
                  </option>
                ))}
            </optgroup>
          )}
          {/* Already-matched PO — show so user can see what was auto-picked */}
          {line.matched_po_id && availablePos.some((p) => p.id === line.matched_po_id && p.status !== "unprocessed") && (
            <optgroup label="Auto-matched (already used)">
              {availablePos
                .filter((p) => p.id === line.matched_po_id)
                .map((po) => (
                  <option key={po.id} value={po.id}>
                    ✅ {po.item_code ? `[${po.item_code}] ` : ""}{(po.description ?? po.id).slice(0, 55)}
                  </option>
                ))}
            </optgroup>
          )}
        </select>
      </td>
      <td className="px-1 py-1 text-center">
        <input
          type="checkbox"
          checked={!!line.user_confirmed}
          onChange={onToggle}
          aria-label="Confirm line"
          className="size-4 accent-primary cursor-pointer"
        />
      </td>
    </tr>
  );
}
