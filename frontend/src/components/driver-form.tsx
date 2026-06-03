"use client";

import type { UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { toApiError } from "@/lib/api/error";
import type { DriverCreateValues } from "@/lib/validation/drivers";

/**
 * Shared driver fields. Create + edit share one value shape (`DriverCreateValues`);
 * on edit the password is optional ("leave blank to keep"). Parent owns `<Form>` + submit.
 */
export function DriverFormFields({
  form,
  mode,
}: {
  form: UseFormReturn<DriverCreateValues>;
  mode: "create" | "edit";
}) {
  return (
    <div className="grid gap-4">
      <FormField
        control={form.control}
        name="email"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Email</FormLabel>
            <FormControl>
              <Input type="email" autoComplete="off" placeholder="driver@transit.app" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="password"
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              Password
              {mode === "edit" && (
                <span className="ml-1 font-normal text-muted-foreground">
                  (leave blank to keep)
                </span>
              )}
            </FormLabel>
            <FormControl>
              <Input
                type="password"
                autoComplete="new-password"
                placeholder={mode === "create" ? "At least 8 characters" : "••••••••"}
                {...field}
                value={field.value ?? ""}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="full_name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Full name</FormLabel>
            <FormControl>
              <Input placeholder="Asha Sharma" {...field} value={field.value ?? ""} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="phone"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Phone</FormLabel>
            <FormControl>
              <Input placeholder="98XXXXXXXX" {...field} value={field.value ?? ""} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </div>
  );
}

/** Map backend envelope errors for driver writes onto the form / a toast. */
export function mapDriverError(err: unknown, form: UseFormReturn<DriverCreateValues>): void {
  const apiError = toApiError(err);
  const fields: Array<keyof DriverCreateValues> = ["email", "password", "full_name", "phone"];
  let mapped = false;

  for (const e of apiError.errors) {
    if (e.field && (fields as string[]).includes(e.field)) {
      form.setError(e.field as keyof DriverCreateValues, { message: e.detail });
      mapped = true;
    }
  }
  if (apiError.has("duplicate_email")) {
    form.setError("email", { message: "This email is already registered." });
    mapped = true;
  }
  if (!mapped) toast.error(apiError.message);
}
