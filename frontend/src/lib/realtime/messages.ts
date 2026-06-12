/**
 * Zod schemas for the WebSocket wire protocol (see `realtime/` on the backend).
 *
 * Inbound (server → client) frames are one of three shapes, discriminated below.
 * Decimals (`lat/lng/speed/heading`) arrive as STRINGS and `trip_id` as a STRING —
 * `parseFloat`/`Number` them before any math. Outbound driver points are plain
 * numbers (the consumer's `LiveGpsPointSerializer` accepts either; the server stamps
 * the timestamp itself for live points).
 */

import { z } from "zod";

/** Live GPS position broadcast for a trip. Decimals + `trip_id` are strings; `ts` is ISO-8601. */
export const locationEventSchema = z.object({
  lat: z.string(),
  lng: z.string(),
  speed: z.string(),
  heading: z.string().nullable(),
  trip_id: z.string(),
  ts: z.string(),
});
export type LocationEvent = z.infer<typeof locationEventSchema>;

/** Lifecycle frame emitted when a trip ends. */
export const tripCompletedSchema = z.object({
  event: z.literal("TRIP_COMPLETED"),
});
export type TripCompletedEvent = z.infer<typeof tripCompletedSchema>;

/** Error frame returned to the driver for a malformed GPS point (socket stays open). */
export const gpsErrorSchema = z.object({
  error: z.literal("invalid_gps_point"),
  detail: z.unknown().optional(),
});
export type GpsErrorEvent = z.infer<typeof gpsErrorSchema>;

/**
 * Any inbound server frame. Order matters: the lifecycle/error frames are tried before
 * the location frame because all three are non-strict objects — the distinctive
 * `event`/`error` keys disambiguate them first.
 */
export const serverMessageSchema = z.union([
  tripCompletedSchema,
  gpsErrorSchema,
  locationEventSchema,
]);
export type ServerMessage = z.infer<typeof serverMessageSchema>;

/** Outbound driver GPS point (no timestamp — the server stamps live points). */
export const outboundGpsSchema = z.object({
  lat: z.number(),
  lng: z.number(),
  speed: z.number(),
  heading: z.number().nullable().optional(),
});
export type OutboundGps = z.infer<typeof outboundGpsSchema>;

/** Parse + validate a raw inbound frame; returns null for anything unrecognized. */
export function parseServerMessage(raw: unknown): ServerMessage | null {
  const result = serverMessageSchema.safeParse(raw);
  return result.success ? result.data : null;
}

/** Narrowing helpers for the discriminated union. */
export const isLocationEvent = (m: ServerMessage): m is LocationEvent =>
  "lat" in m && "trip_id" in m;
export const isTripCompleted = (m: ServerMessage): m is TripCompletedEvent =>
  "event" in m && m.event === "TRIP_COMPLETED";
export const isGpsError = (m: ServerMessage): m is GpsErrorEvent =>
  "error" in m && m.error === "invalid_gps_point";

/**
 * Admin alerts stream (`/ws/alerts/`). This socket only ever emits incident frames, which
 * mirror the REST `Alert` shape, so it's parsed on its own rather than via the trip union.
 * Loose on the extra fields (trip/driver/payload) — the UI reads them defensively.
 */
export const alertEventSchema = z.object({
  id: z.number(),
  type: z.string(),
  severity: z.enum(["info", "warning", "critical"]),
  message: z.string(),
  status: z.enum(["open", "acknowledged"]),
  created_at: z.string(),
});
export type AlertEvent = z.infer<typeof alertEventSchema>;

/** Parse + validate a raw `/ws/alerts/` frame; returns null for anything unrecognized. */
export function parseAlertEvent(raw: unknown): AlertEvent | null {
  const result = alertEventSchema.safeParse(raw);
  return result.success ? result.data : null;
}
