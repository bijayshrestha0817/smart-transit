"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { DriverFormFields, mapDriverError } from "@/components/driver-form";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { getDriver, updateDriver } from "@/lib/api/drivers";
import { ApiError, toApiError } from "@/lib/api/error";
import type { Driver } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { driverEditSchema, type DriverCreateValues } from "@/lib/validation/drivers";

export default function EditDriverPage() {
  const { id } = useParams<{ id: string }>();
  const driverId = Number(id);
  const valid = Number.isFinite(driverId) && driverId > 0;
  const queryClient = useQueryClient();

  const query = useQuery<Driver, ApiError>({
    queryKey: ["admin", "driver", driverId],
    queryFn: () => getDriver(driverId),
    enabled: valid,
  });

  const form = useForm<DriverCreateValues>({
    resolver: zodResolver(driverEditSchema),
    defaultValues: { email: "", password: "", full_name: "", phone: "" },
  });

  useEffect(() => {
    if (query.data) {
      form.reset({
        email: query.data.email,
        password: "",
        full_name: query.data.full_name ?? "",
        phone: query.data.phone ?? "",
      });
    }
  }, [query.data, form]);

  const mutation = useMutation<Driver, ApiError, DriverCreateValues>({
    mutationFn: (values) =>
      updateDriver(driverId, {
        email: values.email,
        full_name: values.full_name || undefined,
        phone: values.phone || undefined,
        ...(values.password ? { password: values.password } : {}),
      }),
    onSuccess: () => {
      toast.success("Driver updated.");
      queryClient.invalidateQueries({ queryKey: ["admin", "driver", driverId] });
      queryClient.invalidateQueries({ queryKey: ["admin", "drivers"] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.drivers });
    },
    onError: (err) => mapDriverError(err, form),
  });

  return (
    <div className="mx-auto grid w-full max-w-xl gap-6">
      <Link
        href="/admin/drivers"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Drivers
      </Link>

      {!valid || query.isError ? (
        <p className="rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
          {!valid || (query.error && toApiError(query.error).status === 404)
            ? "Driver not found."
            : "Could not load this driver."}
        </p>
      ) : query.isLoading || !query.data ? (
        <div className="flex justify-center py-16">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <header>
            <h1 className="font-display text-2xl font-semibold tracking-tight">Edit driver</h1>
            <p className="mt-1 text-sm text-muted-foreground">{query.data.email}</p>
          </header>

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
              className="grid gap-5"
              noValidate
            >
              <DriverFormFields form={form} mode="edit" />
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
