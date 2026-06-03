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
