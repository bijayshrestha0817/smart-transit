"use client";

import { useState } from "react";
import { useFieldArray, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { assignStops } from "@/lib/api/routes";
import { ApiError, toApiError } from "@/lib/api/error";
import type { BusStop } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { stopsEditorSchema, toSixDp, type StopsEditorValues } from "@/lib/validation/routes";

/**
 * Ordered editor for a route's stops. Saving runs the backend's DESTRUCTIVE
 * full-replace (`POST /admin/routes/{id}/stops/`), so it sits behind a confirm.
 * `sequence` is derived from row order; lat/lng are rounded to 6 dp before submit.
 */
export function StopsEditor({
  routeId,
  initialStops,
}: {
  routeId: number;
  initialStops: BusStop[];
}) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const form = useForm<StopsEditorValues>({
    resolver: zodResolver(stopsEditorSchema),
    defaultValues: {
      stops: initialStops.map((s) => ({ name: s.name, lat: s.lat, lng: s.lng })),
    },
  });
  const { fields, append, remove, move } = useFieldArray({
    control: form.control,
    name: "stops",
  });

  const mutation = useMutation<void, ApiError, StopsEditorValues>({
    mutationFn: (values) =>
      assignStops(
        routeId,
        values.stops.map((s, i) => ({
          name: s.name,
          lat: toSixDp(s.lat),
          lng: toSixDp(s.lng),
          sequence: i + 1,
        })),
      ),
    onSuccess: () => {
      toast.success("Stops saved.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.route(routeId) });
      queryClient.invalidateQueries({ queryKey: ["admin", "routes"] });
      setConfirmOpen(false);
    },
    onError: (err) => {
      const apiError = toApiError(err);
      let mapped = false;
      for (const e of apiError.errors) {
        if (e.field && e.field.startsWith("stops.")) {
          form.setError(e.field as FieldPath<StopsEditorValues>, { message: e.detail });
          mapped = true;
        }
      }
      toast.error(mapped ? "Fix the highlighted stops." : apiError.message);
      setConfirmOpen(false);
    },
  });

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(() => setConfirmOpen(true))}
        className="grid gap-3"
        noValidate
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-medium">Stops</h2>
            <p className="text-xs text-muted-foreground">
              In order, top to bottom. Saving replaces all stops on this route.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => append({ name: "", lat: "", lng: "" })}
          >
            <Plus className="size-4" />
            Add stop
          </Button>
        </div>

        {fields.length === 0 ? (
          <p className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
            No stops yet. Add the first one.
          </p>
        ) : (
          <ol className="grid gap-2">
            {fields.map((row, index) => (
              <li
                key={row.id}
                className="grid grid-cols-[auto_1fr_auto] items-start gap-2 rounded-lg border p-2 sm:grid-cols-[auto_2fr_1fr_1fr_auto]"
              >
                <span className="mt-1.5 grid size-7 shrink-0 place-items-center rounded-md bg-muted text-xs font-medium">
                  {index + 1}
                </span>
                <FormField
                  control={form.control}
                  name={`stops.${index}.name`}
                  render={({ field }) => (
                    <FormItem className="col-span-2 sm:col-span-1">
                      <FormControl>
                        <Input placeholder="Stop name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.lat`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input placeholder="lat" inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name={`stops.${index}.lng`}
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Input placeholder="lng" inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex items-center gap-0.5">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => move(index, index - 1)}
                    disabled={index === 0}
                    aria-label="Move up"
                  >
                    <ArrowUp className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => move(index, index + 1)}
                    disabled={index === fields.length - 1}
                    aria-label="Move down"
                  >
                    <ArrowDown className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => remove(index)}
                    aria-label="Remove stop"
                  >
                    <Trash2 className="size-4 text-muted-foreground" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        )}

        <div className="flex justify-end">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Save stops"}
          </Button>
        </div>
      </form>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Replace all stops?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the route&apos;s current stops and saves this list in order. It
              can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => mutation.mutate(form.getValues())}
            >
              Replace stops
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Form>
  );
}
