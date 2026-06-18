import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ─── Business timezone ──────────────────────────────────────────────────────
// The business operates from PST (America/Los_Angeles). All "today" / day-grouping
// logic must use this zone so users in other zones never see a run from the
// business's "today" labelled as yesterday (or vice versa).
export const BUSINESS_TZ = "America/Los_Angeles";

/** Return YYYY-MM-DD for the given date as it falls in the business timezone. */
export function businessDayKey(d: Date | string = new Date()): string {
  const date = typeof d === "string" ? new Date(d) : d;
  if (Number.isNaN(date.getTime())) {
    // Already a YYYY-MM-DD-ish string — keep first 10 chars.
    return String(d).slice(0, 10);
  }
  // en-CA formats as YYYY-MM-DD which is exactly what we want.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: BUSINESS_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
