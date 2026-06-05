"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, MapPin } from "lucide-react";

import { RouteLiveSection } from "@/components/route-live-section";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getRoute } from "@/lib/api/routes";
import { ApiError, toApiError } from "@/lib/api/error";
import type { BusStop, RouteDetail } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";

export default function RouteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const routeId = Number(id);
  const valid = Number.isFinite(routeId) && routeId > 0;

  const query = useQuery<RouteDetail, ApiError>({
    queryKey: QUERY_KEYS.route(routeId),
    queryFn: () => getRoute(routeId),
    enabled: valid,
  });

  return (
    <div className="grid gap-6">
      <Link
        href="/passenger/routes"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        All routes
      </Link>

      {!valid || query.isError ? (
        <DetailError error={query.error} invalid={!valid} />
      ) : query.isLoading || !query.data ? (
        <DetailSkeleton />
      ) : (
        <RouteContent route={query.data} />
      )}
    </div>
  );
}

function RouteContent({ route }: { route: RouteDetail }) {
  return (
    <div className="grid gap-6">
      <header>
        <div className="flex items-center gap-3">
          <span
            className="size-5 shrink-0 rounded-full ring-1 ring-border"
            style={{ backgroundColor: route.color }}
            aria-hidden
          />
          <h1 className="font-display text-3xl font-semibold tracking-tight">{route.name}</h1>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          ~{route.estimated_duration} min end to end · {route.stops.length}{" "}
          {route.stops.length === 1 ? "stop" : "stops"} · {formatMoney(route.fare)} per ride
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stops</CardTitle>
        </CardHeader>
        <CardContent>
          {route.stops.length === 0 ? (
            <p className="text-sm text-muted-foreground">No stops added to this route yet.</p>
          ) : (
            <ol className="grid gap-0">
              {route.stops.map((stop, index) => (
                <StopRow key={stop.id} stop={stop} last={index === route.stops.length - 1} />
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <RouteLiveSection routeId={route.id} stops={route.stops} />
    </div>
  );
}

function StopRow({ stop, last }: { stop: BusStop; last: boolean }) {
  return (
    <li className="relative flex items-start gap-3 pb-5 last:pb-0">
      <div className="flex flex-col items-center">
        <span className="grid size-6 shrink-0 place-items-center rounded-full border bg-background text-[0.65rem] font-medium">
          {stop.sequence}
        </span>
        {!last && <span className="mt-1 w-px flex-1 bg-border" aria-hidden />}
      </div>
      <div className="-mt-0.5">
        <p className="text-sm font-medium">{stop.name}</p>
        <p className="label-mono text-[0.6rem] text-muted-foreground">
          {stop.lat}, {stop.lng}
        </p>
      </div>
    </li>
  );
}

function DetailSkeleton() {
  return (
    <div className="grid gap-6">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

function DetailError({ error, invalid }: { error: ApiError | null; invalid: boolean }) {
  const notFound = invalid || (error ? toApiError(error).status === 404 : false);
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      {notFound ? (
        <>
          <MapPin className="size-5" />
          <p>Route not found.</p>
        </>
      ) : (
        <>
          <AlertCircle className="size-5 text-destructive" />
          <p>{error ? toApiError(error).message : "Could not load this route."}</p>
        </>
      )}
    </div>
  );
}
