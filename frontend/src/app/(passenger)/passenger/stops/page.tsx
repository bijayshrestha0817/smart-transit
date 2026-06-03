"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, LocateFixed, MapPin, Search, X } from "lucide-react";
import { toast } from "sonner";

import { CursorPager } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listRoutes } from "@/lib/api/routes";
import { listStops, type StopListParams } from "@/lib/api/stops";
import { toApiError } from "@/lib/api/error";
import type { BusStop, Route } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

const NEAR_RADIUS_KM = 2;
const ALL_ROUTES = "all";

export default function PassengerStopsPage() {
  const [search, setSearch] = useState("");
  const [routeFilter, setRouteFilter] = useState<string>(ALL_ROUTES);
  const [near, setNear] = useState<string | undefined>(undefined);
  const [locating, setLocating] = useState(false);
  const debouncedSearch = useDebouncedValue(search.trim());

  // Route options for the filter + to label each stop with its route.
  const routesQuery = useQuery({
    queryKey: QUERY_KEYS.routes({ options: true }),
    queryFn: () => listRoutes({ page_size: 100, ordering: "name" }),
  });
  const routeOptions = routesQuery.data?.rows ?? [];
  const routeById = new Map<number, Route>(routeOptions.map((r) => [r.id, r]));

  const params: StopListParams = {
    search: debouncedSearch || undefined,
    route: routeFilter === ALL_ROUTES ? undefined : Number(routeFilter),
    near,
    radius: near ? NEAR_RADIUS_KM : undefined,
  };
  const list = useCursorList<BusStop, StopListParams>({
    queryKey: QUERY_KEYS.stops(params),
    params,
    fetchPage: (args) => listStops(args),
  });

  function locateMe() {
    if (!navigator.geolocation) {
      toast.error("Location isn't available in this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(6);
        const lng = pos.coords.longitude.toFixed(6);
        setNear(`${lat},${lng}`);
        setLocating(false);
      },
      () => {
        toast.error("Couldn't get your location.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  return (
    <div className="grid gap-6">
      <header>
        <p className="label-mono text-xs text-muted-foreground">Browse</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Stops</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Find a stop by name, filter by route, or show the ones nearest you.
        </p>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search stops by name…"
            className="pl-9"
            aria-label="Search stops"
          />
        </div>
        <Select value={routeFilter} onValueChange={setRouteFilter}>
          <SelectTrigger className="sm:w-52" aria-label="Filter by route">
            <SelectValue placeholder="All routes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_ROUTES}>All routes</SelectItem>
            {routeOptions.map((r) => (
              <SelectItem key={r.id} value={String(r.id)}>
                {r.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {near ? (
          <Button variant="secondary" onClick={() => setNear(undefined)}>
            <X className="size-4" />
            Near me
          </Button>
        ) : (
          <Button variant="outline" onClick={locateMe} disabled={locating}>
            <LocateFixed className="size-4" />
            {locating ? "Locating…" : "Near me"}
          </Button>
        )}
      </div>

      {near && (
        <p className="-mt-2 text-xs text-muted-foreground">
          Showing stops within {NEAR_RADIUS_KM} km of your location.
        </p>
      )}

      {list.isError ? (
        <ErrorState message={toApiError(list.error).message} />
      ) : list.isLoading ? (
        <div className="grid gap-2.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      ) : list.rows.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-2.5">
          {list.rows.map((stop) => (
            <StopCard key={stop.id} stop={stop} route={routeById.get(stop.route)} />
          ))}
        </div>
      )}

      <CursorPager
        hasPrev={list.hasPrev}
        hasNext={list.hasNext}
        onPrev={list.prev}
        onNext={list.next}
        isFetching={list.isFetching}
      />
    </div>
  );
}

function StopCard({ stop, route }: { stop: BusStop; route?: Route }) {
  return (
    <Card className="py-0">
      <CardContent className="flex items-center justify-between gap-4 px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-secondary-foreground">
            <MapPin className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{stop.name}</p>
            <p className="label-mono text-[0.6rem] text-muted-foreground">
              {stop.lat}, {stop.lng}
            </p>
          </div>
        </div>
        {route && (
          <Badge variant="secondary" className="shrink-0 gap-1.5">
            <span
              className="size-2 rounded-full"
              style={{ backgroundColor: route.color }}
              aria-hidden
            />
            {route.name}
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      No stops found.
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 py-12 text-sm text-destructive">
      <AlertCircle className="size-4" />
      {message}
    </div>
  );
}
