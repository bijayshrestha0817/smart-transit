/** Shared formatting helpers for the admin/browse tables. */

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
