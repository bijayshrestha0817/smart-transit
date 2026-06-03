"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { BusFormFields, mapBusError } from "@/components/bus-form";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { createBus, type BusInput } from "@/lib/api/buses";
import { listDriverOptions } from "@/lib/api/drivers";
import { ApiError } from "@/lib/api/error";
import type { Bus } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { busSchema, type BusValues } from "@/lib/validation/buses";

export default function NewBusPage() {
  const router = useRouter();
  const driversQuery = useQuery({ queryKey: QUERY_KEYS.drivers, queryFn: listDriverOptions });

  const form = useForm<BusValues>({
    resolver: zodResolver(busSchema) as unknown as Resolver<BusValues>,
    defaultValues: { plate: "", status: "idle", assigned_driver: null },
  });

  const mutation = useMutation<Bus, ApiError, BusValues>({
    mutationFn: (values) => createBus(values as BusInput),
    onSuccess: () => {
      toast.success("Bus created.");
      router.replace("/admin/buses");
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

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight">New bus</h1>
        <p className="mt-1 text-sm text-muted-foreground">Register a vehicle in the fleet.</p>
      </header>

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="grid gap-5"
          noValidate
        >
          <BusFormFields form={form} drivers={driversQuery.data ?? []} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" asChild>
              <Link href="/admin/buses">Cancel</Link>
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create bus"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
