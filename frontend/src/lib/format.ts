/** Shared formatting helpers for the admin/browse tables. */

import type { Eta } from "@/lib/api/types";

/**
 * Render a baseline ETA as a short human label, or `null` when there's nothing to show
 * (unavailable estimate). Sub-minute reads as "Due"; otherwise names the next stop when
 * known, else a plain "Arriving in N min".
 */
export function formatEta(eta: Eta | null | undefined): string | null {
  if (!eta || eta.source === "unavailable" || eta.minutes == null) return null;
  if (eta.minutes < 1) return eta.next_stop ? `Due at ${eta.next_stop}` : "Due";
  return eta.next_stop ? `${eta.next_stop} in ${eta.minutes} min` : `Arriving in ${eta.minutes} min`;
}

/** Format an ISO timestamp as a short local date, or an em dash if invalid. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}

/** Format an ISO timestamp as a short local date + time, or an em dash if invalid. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

/**
 * Format a decimal money STRING (the backend sends amounts as strings) as `Rs 25.00`.
 * NPR matches the Khalti/eSewa context; `parseFloat` only for display rounding.
 */
export function formatMoney(value: string | number): string {
  const n = Number(value);
  return Number.isNaN(n) ? "—" : `Rs ${n.toFixed(2)}`;
}
