/**
 * Zod schemas for the auth forms.
 *
 * These mirror the backend serializer rules (email format, required fields, the
 * `new_password` field name) for fast inline feedback. The backend remains the
 * source of truth for full password-strength validation; those failures come back
 * as envelope field errors and are surfaced per-field at submit time.
 */

import { z } from "zod";

const email = z.string().min(1, "Email is required").email("Enter a valid email address");
const password = z.string().min(1, "Password is required");

export const loginSchema = z.object({
  email,
  password,
});
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  full_name: z.string().min(1, "Your name is required").max(150, "Name is too long"),
  email,
  phone: z.string().max(20, "Phone number is too long").optional().or(z.literal("")),
  // Mirror Django's default min length; backend enforces the full policy.
  password: z.string().min(8, "Password must be at least 8 characters"),
});
export type RegisterValues = z.infer<typeof registerSchema>;

export const forgotPasswordSchema = z.object({
  email,
});
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((vals) => vals.new_password === vals.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;
