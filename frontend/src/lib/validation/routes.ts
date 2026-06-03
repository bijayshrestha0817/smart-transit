/**
 * Zod schemas for the admin route form + in-route stops editor.
 *
 * Mirrors `RouteInput` / `StopInput` (lib/api/routes.ts) and the backend serializer
 * rules: a `#`-hex color, a positive `estimated_duration`, and decimal `lat`/`lng`
 * that must be rounded to 6 dp before submit (the backend `DecimalField(9,6)` rejects
 * more, and browser geolocation emits 10+ digits). The backend stays the source of
 * truth; these give fast inline feedback.
 */

import { z } from "zod";

/** Matches the backend color RegexValidator: `#RGB` or `#RRGGBB`. */
const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Round a coordinate to 6 decimal places before sending (Implementation rule 6). */
export const toSixDp = (value: string | number): string => Number(value).toFixed(6);

export const routeSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  color: z.string().regex(HEX_COLOR, "Enter a hex color like #1e88e5"),
  estimated_duration: z.coerce
    .number()
    .int("Must be a whole number of minutes")
    .min(1, "Must be at least 1 minute"),
});
export type RouteValues = z.infer<typeof routeSchema>;

/** A coordinate text field: required and parseable as a number. */
const coord = z
  .string()
  .min(1, "Required")
  .refine((v) => v.trim() !== "" && !Number.isNaN(Number(v)), "Must be a number");

// `sequence` is derived from row order at save time, so the editable row is just
// name + coords.
export const stopRowSchema = z.object({
  name: z.string().min(1, "Stop name is required").max(120, "Name is too long"),
  lat: coord,
  lng: coord,
});
export type StopRowValues = z.infer<typeof stopRowSchema>;

export const stopsEditorSchema = z.object({
  stops: z.array(stopRowSchema),
});
export type StopsEditorValues = z.infer<typeof stopsEditorSchema>;
