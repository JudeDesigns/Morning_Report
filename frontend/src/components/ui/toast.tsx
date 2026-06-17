"use client";

/**
 * Minimal toast notification system.
 *
 * Usage:
 *   1. Render <Toaster /> once in the app shell (already done in providers).
 *   2. Import { toast } and call toast.success("..."), toast.error("..."),
 *      toast.info("...") from anywhere in the React tree.
 *
 * No external dependency — just React state + a module-level event bus so it
 * works from event handlers and async callbacks alike.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
  duration: number;
}

type Listener = (toast: ToastItem) => void;
const listeners = new Set<Listener>();
let nextId = 1;

function emit(message: string, variant: ToastVariant, duration: number) {
  const t: ToastItem = { id: nextId++, message, variant, duration };
  listeners.forEach((l) => l(t));
}

export const toast = {
  success: (message: string, duration = 3500) => emit(message, "success", duration),
  error: (message: string, duration = 6000) => emit(message, "error", duration),
  info: (message: string, duration = 3500) => emit(message, "info", duration),
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handler: Listener = (t) => {
      setItems((prev) => [...prev, t]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((i) => i.id !== t.id));
      }, t.duration);
    };
    listeners.add(handler);
    return () => {
      listeners.delete(handler);
    };
  }, []);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="pointer-events-none fixed bottom-4 right-4 z-[200] flex w-full max-w-sm flex-col gap-2">
      {items.map((t) => (
        <ToastView key={t.id} item={t} onDismiss={() => setItems((p) => p.filter((i) => i.id !== t.id))} />
      ))}
    </div>,
    document.body,
  );
}

function ToastView({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const Icon = item.variant === "success" ? CheckCircle2 : item.variant === "error" ? AlertTriangle : Info;
  return (
    <div
      className={cn(
        "pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-card px-3.5 py-2.5 shadow-lg",
        item.variant === "success" && "border-emerald-300 dark:border-emerald-900/60",
        item.variant === "error" && "border-rose-300 dark:border-rose-900/60",
        item.variant === "info" && "border-border",
      )}
      role={item.variant === "error" ? "alert" : "status"}
    >
      <Icon
        className={cn(
          "mt-0.5 size-4 shrink-0",
          item.variant === "success" && "text-emerald-600 dark:text-emerald-400",
          item.variant === "error" && "text-rose-600 dark:text-rose-400",
          item.variant === "info" && "text-muted-foreground",
        )}
      />
      <p className="flex-1 text-xs leading-snug text-foreground">{item.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="Dismiss notification"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
