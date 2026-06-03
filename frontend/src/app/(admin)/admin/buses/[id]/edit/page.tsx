"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { BusFormFields, mapBusError } from "@/components/bus-form";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { getBus, updateBus, type BusInput } from "@/lib/api/buses";
import { listDriverOptions } from "@/lib/api/drivers";
import { ApiError, toApiError } from "@/lib/api/error";
import type { Bus } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { busSchema, type BusValues } from "@/lib/validation/buses";

export default function EditBusPage() {
  const { id } = useParams<{ id: string }>();
  const busId = Number(id);
  const valid = Number.isFinite(busId) && busId > 0;
  const queryClient = useQueryClient();

  const query = useQuery<Bus, ApiError>({
    queryKey: ["admin", "bus", busId],
    queryFn: () => getBus(busId),
    enabled: valid,
  });
  const driversQuery = useQuery({ queryKey: QUERY_KEYS.drivers, queryFn: listDriverOptions });

  const form = useForm<BusValues>({
    resolver: zodResolver(busSchema) as unknown as Resolver<BusValues>,
    defaultValues: { plate: "", status: "idle", assigned_driver: null },
  });

  useEffect(() => {
    if (query.data) {
      form.reset({
        plate: query.data.plate,
        capacity: query.data.capacity,
        status: query.data.status,
        assigned_driver: query.data.assigned_driver,
      });
    }
  }, [query.data, form]);

  const mutation = useMutation<Bus, ApiError, BusValues>({
    mutationFn: (values) => updateBus(busId, values as BusInput),
    onSuccess: () => {
      toast.success("Bus updated.");
      queryClient.invalidateQueries({ queryKey: ["admin", "bus", busId] });
      queryClient.invalidateQueries({ queryKey: ["admin", "buses"] });
    },
    onError: (err) => mapBusError(err, form),
  });

  return (
    <div className="mx-auto grid w-full max-w-xl gap-6">
      <Link
        href="/admin/buses"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Buses
      </Link>

      {!valid || query.isError ? (
        <p className="rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
          {!valid || (query.error && toApiError(query.error).status === 404)
            ? "Bus not found."
            : "Could not load this bus."}
        </p>
      ) : query.isLoading || !query.data ? (
        <div className="flex justify-center py-16">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <header>
            <h1 className="font-display text-2xl font-semibold tracking-tight">Edit bus</h1>
            <p className="mt-1 text-sm text-muted-foreground">{query.data.plate}</p>
          </header>

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
              className="grid gap-5"
              noValidate
            >
              <BusFormFields form={form} drivers={driversQuery.data ?? []} />
              <div className="flex justify-end">
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? "Saving…" : "Save changes"}
                </Button>
              </div>
            </form>
          </Form>
        </>
      )}
    </div>
  );
}
