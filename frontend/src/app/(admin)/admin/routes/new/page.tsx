"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { RouteFormFields, mapRouteError } from "@/components/route-form";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { createRoute, type RouteInput } from "@/lib/api/routes";
import { ApiError } from "@/lib/api/error";
import type { RouteDetail } from "@/lib/api/types";
import { routeSchema, type RouteValues } from "@/lib/validation/routes";

export default function NewRoutePage() {
  const router = useRouter();
  const form = useForm<RouteValues>({
    // z.coerce makes the resolver's input type `unknown`; cast to the output type.
    resolver: zodResolver(routeSchema) as unknown as Resolver<RouteValues>,
    defaultValues: { name: "", color: "#2563eb" },
  });

  const mutation = useMutation<RouteDetail, ApiError, RouteValues>({
    mutationFn: (values) => createRoute(values as RouteInput),
    onSuccess: (route) => {
      toast.success("Route created — now add its stops.");
      router.replace(`/admin/routes/${route.id}/edit`);
    },
    onError: (err) => mapRouteError(err, form),
  });

  return (
    <div className="mx-auto grid w-full max-w-xl gap-6">
      <Link
        href="/admin/routes"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Routes
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight">New route</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create the route, then add its stops on the next step.
        </p>
      </header>

      <Form {...form}>
        <form
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          className="grid gap-5"
          noValidate
        >
          <RouteFormFields form={form} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" asChild>
              <Link href="/admin/routes">Cancel</Link>
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create route"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
