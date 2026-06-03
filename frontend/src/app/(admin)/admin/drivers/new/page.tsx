"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { DriverFormFields, mapDriverError } from "@/components/driver-form";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { createDriver } from "@/lib/api/drivers";
import { ApiError } from "@/lib/api/error";
import type { Driver } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { driverCreateSchema, type DriverCreateValues } from "@/lib/validation/drivers";

export default function NewDriverPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const form = useForm<DriverCreateValues>({
    resolver: zodResolver(driverCreateSchema),
    defaultValues: { email: "", password: "", full_name: "", phone: "" },
  });

  const mutation = useMutation<Driver, ApiError, DriverCreateValues>({
    mutationFn: (values) =>
      createDriver({
        email: values.email,
        password: values.password,
        full_name: values.full_name || undefined,
        phone: values.phone || undefined,
      }),
    onSuccess: () => {
      toast.success("Driver created.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.drivers });
      router.replace("/admin/drivers");
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

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight">New driver</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The account is created already verified and can sign in immediately.
        </p>
      </header>

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="grid gap-5"
          noValidate
        >
          <DriverFormFields form={form} mode="create" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" asChild>
              <Link href="/admin/drivers">Cancel</Link>
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create driver"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
