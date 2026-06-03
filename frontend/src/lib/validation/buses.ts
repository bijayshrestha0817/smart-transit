/**
 * Zod schemas for the admin bus form + the assign-driver / maintenance dialogs.
 *
 * Mirrors `BusInput` (lib/api/buses.ts). `assigned_driver` is preprocessed so the
 * Select's "none"/"" maps to null rather than coercing to 0. Duplicate plates come
 * back from the backend as a `duplicate_plate` envelope code, surfaced at submit.
 */

import { z } from "zod";

import type { BusStatus } from "@/lib/api/types";

/** Kept in sync with the `BusStatus` union via `satisfies`. */
export const BUS_STATUSES = [
  "active",
  "idle",
  "maintenance",
  "retired",
] as const satisfies readonly BusStatus[];

export const busSchema = z.object({
  plate: z.string().min(1, "Plate is required").max(20, "Plate is too long"),
  capacity: z.coerce
    .number()
    .int("Must be a whole number")
    .min(1, "Capacity must be at least 1"),
  status: z.enum(BUS_STATUSES).default("idle"),
  assigned_driver: z
    .preprocess(
      (v) => (v === "" || v === "none" || v === undefined || v === null ? null : Number(v)),
      z.number().int().positive().nullable(),
    )
    .optional(),
});
export type BusValues = z.infer<typeof busSchema>;

export const assignDriverSchema = z.object({
  driver_id: z.coerce.number().int().positive("Select a driver"),
});
export type AssignDriverValues = z.infer<typeof assignDriverSchema>;

export const maintenanceSchema = z.object({
  note: z.string().max(500, "Note is too long").optional(),
});
export type MaintenanceValues = z.infer<typeof maintenanceSchema>;
