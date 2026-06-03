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
import type { RouteValues } from "@/lib/validation/routes";

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Shared route fields (name, color, duration). The parent owns the `<Form>` + submit. */
export function RouteFormFields({ form }: { form: UseFormReturn<RouteValues> }) {
  const color = form.watch("color");

  return (
    <div className="grid gap-4">
      <FormField
        control={form.control}
        name="name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Name</FormLabel>
            <FormControl>
              <Input placeholder="e.g. Ring Road" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="color"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Color</FormLabel>
            <FormControl>
              <div className="flex items-center gap-2">
                <span
                  className="size-9 shrink-0 rounded-md ring-1 ring-border"
                  style={{ backgroundColor: HEX.test(color ?? "") ? color : "transparent" }}
                  aria-hidden
                />
                <Input placeholder="#1e88e5" {...field} />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="estimated_duration"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Estimated duration (minutes)</FormLabel>
            <FormControl>
              <Input
                type="number"
                min={1}
                placeholder="45"
                {...field}
                value={field.value ?? ""}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </div>
  );
}

/** Map backend envelope errors for route writes onto the form / a toast. */
export function mapRouteError(err: unknown, form: UseFormReturn<RouteValues>): void {
  const apiError = toApiError(err);
  const fields: Array<keyof RouteValues> = ["name", "color", "estimated_duration"];
  let mapped = false;

  for (const e of apiError.errors) {
    if (e.field && (fields as string[]).includes(e.field)) {
      form.setError(e.field as keyof RouteValues, { message: e.detail });
      mapped = true;
    }
  }
  if (apiError.has("invalid_color")) {
    form.setError("color", { message: "Enter a valid hex color like #1e88e5." });
    mapped = true;
  }
  if (!mapped) toast.error(apiError.message);
}
