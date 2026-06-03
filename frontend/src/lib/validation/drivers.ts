/**
 * Zod schemas for the admin driver create/edit forms.
 *
 * Mirrors `DriverCreateInput` / `DriverUpdateInput` (lib/api/drivers.ts). Password is
 * required on create (min 8, matching Django's default) and optional on edit (blank =
 * leave unchanged). Duplicate emails come back as a `duplicate_email` envelope code.
 */

import { z } from "zod";

const email = z.string().min(1, "Email is required").email("Enter a valid email address");
const full_name = z.string().max(150, "Name is too long").optional().or(z.literal(""));
const phone = z.string().max(20, "Phone number is too long").optional().or(z.literal(""));

export const driverCreateSchema = z.object({
  email,
  password: z.string().min(8, "Password must be at least 8 characters"),
  full_name,
  phone,
});
export type DriverCreateValues = z.infer<typeof driverCreateSchema>;

export const driverEditSchema = z.object({
  email,
  // Blank = keep the current password; otherwise enforce the min length. Kept as a
  // (possibly empty) string — not optional — so the value type matches the create
  // form and both can share one fields component.
  password: z.string().min(8, "Password must be at least 8 characters").or(z.literal("")),
  full_name,
  phone,
});
export type DriverEditValues = z.infer<typeof driverEditSchema>;
