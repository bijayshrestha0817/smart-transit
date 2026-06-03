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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toApiError } from "@/lib/api/error";
import type { Driver } from "@/lib/api/types";
import { BUS_STATUSES, type BusValues } from "@/lib/validation/buses";

const UNASSIGNED = "none";

/** Shared bus fields (plate, capacity, status, driver). Parent owns `<Form>` + submit. */
export function BusFormFields({
  form,
  drivers,
}: {
  form: UseFormReturn<BusValues>;
  drivers: Driver[];
}) {
  return (
    <div className="grid gap-4">
      <FormField
        control={form.control}
        name="plate"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Plate</FormLabel>
            <FormControl>
              <Input placeholder="BA 1 KHA 1234" {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="capacity"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Capacity</FormLabel>
            <FormControl>
              <Input type="number" min={1} placeholder="40" {...field} value={field.value ?? ""} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="status"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Status</FormLabel>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger className="capitalize">
                  <SelectValue />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {BUS_STATUSES.map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="assigned_driver"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Assigned driver</FormLabel>
            <Select
              value={field.value == null ? UNASSIGNED : String(field.value)}
              onValueChange={(v) => field.onChange(v === UNASSIGNED ? null : Number(v))}
            >
              <FormControl>
                <SelectTrigger>
                  <SelectValue placeholder="Unassigned" />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                {drivers.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>
                    {d.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )}
      />
    </div>
  );
}

/** Map backend envelope errors for bus writes onto the form / a toast. */
export function mapBusError(err: unknown, form: UseFormReturn<BusValues>): void {
  const apiError = toApiError(err);
  const fields: Array<keyof BusValues> = ["plate", "capacity", "status", "assigned_driver"];
  let mapped = false;

  for (const e of apiError.errors) {
    if (e.field && (fields as string[]).includes(e.field)) {
      form.setError(e.field as keyof BusValues, { message: e.detail });
      mapped = true;
    }
  }
  if (apiError.has("duplicate_plate")) {
    form.setError("plate", { message: "A bus with this plate already exists." });
    mapped = true;
  }
  if (apiError.has("invalid_driver")) {
    form.setError("assigned_driver", { message: "Select an active driver." });
    mapped = true;
  }
  if (!mapped) toast.error(apiError.message);
}
