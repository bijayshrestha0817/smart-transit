/**
 * Shared presentation helpers for in-app notifications.
 *
 * Extracted from `notification-bell.tsx` so the bell dropdown and the full-page
 * notifications view render the same label / copy / relative-time for a given
 * notification — one source of truth, no drift.
 */

import {
  BusFront,
  CircleCheck,
  Clock,
  TriangleAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import type { AppNotification, NotificationType } from "@/lib/api/types";

/** Short human label per notification type (kicker / list heading). */
export const LABEL: Record<NotificationType, string> = {
  bus_arriving: "Bus arriving",
  route_delay: "Route delay",
  emergency: "Emergency",
  maintenance_due: "Maintenance due",
  trip_completed: "Trip completed",
};

/**
 * Per-type icon. All names verified to exist as real `lucide-react` exports:
 * BusFront, Clock, TriangleAlert, Wrench, CircleCheck.
 */
export const ICON: Record<NotificationType, LucideIcon> = {
  bus_arriving: BusFront,
  route_delay: Clock,
  emergency: TriangleAlert,
  maintenance_due: Wrench,
  trip_completed: CircleCheck,
};

/** Build a human line from the type + free-form payload. */
export function describe(n: AppNotification): string {
  const p = n.payload_json ?? {};
  const route = typeof p.route_name === "string" ? p.route_name : null;
  switch (n.type) {
    case "trip_completed":
      return route ? `Trip completed on ${route}.` : "A trip you follow has completed.";
    case "bus_arriving":
      return route ? `Your bus is arriving on ${route}.` : "Your bus is arriving.";
    case "route_delay":
      return route ? `Delay reported on ${route}.` : "A delay was reported on your route.";
    case "maintenance_due":
      return typeof p.plate === "string"
        ? `Maintenance due for ${p.plate}.`
        : "A bus needs maintenance.";
    case "emergency":
      return typeof p.message === "string" ? p.message : "Emergency alert.";
    default:
      return LABEL[n.type] ?? "Notification";
  }
}

/** Compact relative time: "just now", "5m ago", "3h ago", "2d ago". */
export function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
