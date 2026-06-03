"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { RouteFormFields, mapRouteError } from "@/components/route-form";
import { StopsEditor } from "@/components/stops-editor";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Separator } from "@/components/ui/separator";
import { getRoute, updateRoute, type RouteInput } from "@/lib/api/routes";
import { ApiError, toApiError } from "@/lib/api/error";
import type { RouteDetail } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { routeSchema, type RouteValues } from "@/lib/validation/routes";

export default function EditRoutePage() {
  const { id } = useParams<{ id: string }>();
  const routeId = Number(id);
  const valid = Number.isFinite(routeId) && routeId > 0;
  const queryClient = useQueryClient();

  const query = useQuery<RouteDetail, ApiError>({
    queryKey: QUERY_KEYS.route(routeId),
    queryFn: () => getRoute(routeId),
    enabled: valid,
  });

  const form = useForm<RouteValues>({
    // z.coerce makes the resolver's input type `unknown`; cast to the output type.
    resolver: zodResolver(routeSchema) as unknown as Resolver<RouteValues>,
    defaultValues: { name: "", color: "#2563eb" },
  });

  useEffect(() => {
    if (query.data) {
      form.reset({
        name: query.data.name,
        color: query.data.color,
        estimated_duration: query.data.estimated_duration,
      });
    }
  }, [query.data, form]);

  const mutation = useMutation<RouteDetail, ApiError, RouteValues>({
    mutationFn: (values) => updateRoute(routeId, values as RouteInput),
    onSuccess: () => {
      toast.success("Route updated.");
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.route(routeId) });
      queryClient.invalidateQueries({ queryKey: ["admin", "routes"] });
    },
    onError: (err) => mapRouteError(err, form),
  });

  return (
    <div className="mx-auto grid w-full max-w-2xl gap-8">
      <Link
        href="/admin/routes"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Routes
      </Link>

      {!valid || query.isError ? (
        <p className="rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
          {!valid
            ? "Route not found."
            : query.error && toApiError(query.error).status === 404
              ? "Route not found."
              : "Could not load this route."}
        </p>
      ) : query.isLoading || !query.data ? (
        <div className="flex justify-center py-16">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <header>
            <h1 className="font-display text-2xl font-semibold tracking-tight">
              Edit route
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">{query.data.name}</p>
          </header>

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
              className="grid gap-5"
              noValidate
            >
              <RouteFormFields form={form} />
              <div className="flex justify-end">
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? "Saving…" : "Save changes"}
                </Button>
              </div>
            </form>
          </Form>

          <Separator />

          <StopsEditor routeId={routeId} initialStops={query.data.stops} />
        </>
      )}
    </div>
  );
}
