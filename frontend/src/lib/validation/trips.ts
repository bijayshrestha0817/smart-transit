/**
 * Zod schemas for the admin trip-scheduling form and the driver passenger-count
 * control. Mirrors `AdminTripInput` (lib/api/trips.ts) and the backend serializer:
 * `bus`/`route`/`driver` are PK selections; `status` is an optional enum. The backend
 * remains the source of truth (codes `invalid_bus`/`invalid_route`/`invalid_driver`);
 * these just give fast inline feedback.
 */

import { z } from "zod";

export const TRIP_STATUSES = ["scheduled", "in_progress", "completed", "cancelled"] as const;

export const adminTripSchema = z.object({
  bus: z.coerce.number().int().positive("Select a bus"),
  route: z.coerce.number().int().positive("Select a route"),
  driver: z.coerce.number().int().positive("Select a driver"),
  status: z.enum(TRIP_STATUSES).optional(),
});
export type AdminTripValues = z.infer<typeof adminTripSchema>;

export const passengerCountSchema = z.object({
  count: z.coerce
    .number()
    .int("Must be a whole number")
    .min(0, "Must be 0 or more")
    .max(1000, "That seems too high"),
});
export type PassengerCountValues = z.infer<typeof passengerCountSchema>;
