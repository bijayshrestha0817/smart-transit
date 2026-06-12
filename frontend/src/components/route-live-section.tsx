"use client";

/**
 * Live section for a passenger's route view: seeds active buses + their last known
 * position from REST (`/trips/active/?route=`), then subscribes to `ws/trip/{id}` per
 * active trip so each bus marker tracks the live stream. WS positions override the REST
 * seed (fan-out happens before DB persist, so the socket leads). A `TRIP_COMPLETED`
 * frame drops the bus and refetches the active list.
 *
 * One `<TripFeed>` child per active trip keeps `useSocket` calls fixed per component
 * instance (rules of hooks) while the set of trips changes by mount/unmount.
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Bus, MapPin, Radio } from "lucide-react";

import { LiveMap, type MapMarker, type MapStop } from "@/components/live-map";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSocket } from "@/hooks/use-socket";
import { ApiError, toApiError } from "@/lib/api/error";
import { activeTrips } from "@/lib/api/trips";
import type { ActiveTrip, BusStop } from "@/lib/api/types";
import {
  isLocationEvent,
  isTripCompleted,
  parseServerMessage,
  type LocationEvent,
} from "@/lib/realtime/messages";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

interface LivePos {
  lat: number;
  lng: number;
  heading: number | null;
}

export function RouteLiveSection({ routeId, stops }: { routeId: number; stops: BusStop[] }) {
  const query = useQuery<ActiveTrip[], ApiError>({
    queryKey: QUERY_KEYS.activeTrips(routeId),
    queryFn: () => activeTrips(routeId),
    enabled: routeId > 0,
    refetchOnWindowFocus: true,
  });
  const refetch = query.refetch;

  // WS-driven positions, keyed by trip id. Seed comes inline from REST last_position.
  const [positions, setPositions] = useState<Record<number, LivePos>>({});
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [focus, setFocus] = useState<{ lat: number; lng: number; nonce: number } | null>(null);

  const handleLocation = useCallback((tripId: number, ev: LocationEvent) => {
    setPositions((prev) => ({
      ...prev,
      [tripId]: {
        lat: Number(ev.lat),
        lng: Number(ev.lng),
        heading: ev.heading != null ? Number(ev.heading) : null,
      },
    }));
  }, []);

  const handleCompleted = useCallback(
    (tripId: number) => {
      setPositions((prev) => {
        const next = { ...prev };
        delete next[tripId];
        return next;
      });
      void refetch();
    },
    [refetch],
  );

  const active = query.data ?? [];

  // Prune the live-position cache to currently-active trips so a missed TRIP_COMPLETED
  // frame can't leave a stale entry around indefinitely (trip ids are DB PKs, never reused).
  const activeIdsKey = active.map((a) => a.trip.id).join(",");
  useEffect(() => {
    const ids = new Set(activeIdsKey ? activeIdsKey.split(",").map(Number) : []);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPositions((prev) => {
      const next: Record<number, LivePos> = {};
      let changed = false;
      for (const key of Object.keys(prev)) {
        const id = Number(key);
        if (ids.has(id)) next[id] = prev[id];
        else changed = true;
      }
      return changed ? next : prev;
    });
  }, [activeIdsKey]);

  const mapStops: MapStop[] = stops.map((s) => ({
    id: s.id,
    lat: Number(s.lat),
    lng: Number(s.lng),
    name: s.name,
  }));
  const polyline: [number, number][] = stops.map((s) => [Number(s.lat), Number(s.lng)]);

  const markers: MapMarker[] = active
    .map((at): MapMarker | null => {
      const live = positions[at.trip.id];
      const seed = at.last_position;
      const lat = live ? live.lat : seed ? Number(seed.lat) : null;
      const lng = live ? live.lng : seed ? Number(seed.lng) : null;
      if (lat == null || lng == null) return null;
      const heading = live ? live.heading : seed?.heading != null ? Number(seed.heading) : null;
      return {
        id: at.trip.id,
        lat,
        lng,
        heading,
        label: `Bus ${at.trip.bus_plate}`,
        color: at.trip.route_color || "#1e88e5",
      };
    })
    .filter((m): m is MapMarker => m !== null);

  // Tap a bus → highlight it + fly the map to its current position.
  const focusBus = (at: ActiveTrip) => {
    setSelectedId(at.trip.id);
    const live = positions[at.trip.id];
    const seed = at.last_position;
    const lat = live ? live.lat : seed ? Number(seed.lat) : null;
    const lng = live ? live.lng : seed ? Number(seed.lng) : null;
    if (lat != null && lng != null) {
      setFocus((f) => ({ lat, lng, nonce: (f?.nonce ?? 0) + 1 }));
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <Radio className="size-4 text-emerald-600 dark:text-emerald-400" />
          Live buses
        </CardTitle>
        {active.length > 0 && (
          <span className="label-mono text-[0.6rem] text-muted-foreground">
            {active.length} active
          </span>
        )}
      </CardHeader>
      <CardContent className="grid gap-4">
        {/* Invisible per-trip subscriptions. */}
        {active.map((at) => (
          <TripFeed
            key={at.trip.id}
            tripId={at.trip.id}
            onLocation={handleLocation}
            onCompleted={handleCompleted}
          />
        ))}

        {query.isError ? (
          <div className="flex items-center justify-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 py-8 text-sm text-destructive">
            <AlertCircle className="size-4" />
            {toApiError(query.error).message}
          </div>
        ) : query.isLoading ? (
          <Skeleton className="h-[360px] w-full rounded-lg" />
        ) : (
          <>
            <div className="overflow-hidden rounded-lg border">
              <LiveMap
                markers={markers}
                stops={mapStops}
                polyline={polyline}
                focus={focus}
                selectedId={selectedId}
                className="h-[360px] w-full"
              />
            </div>
            {active.length === 0 ? (
              <p className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
                <Bus className="size-4" />
                No buses are running on this route right now.
              </p>
            ) : (
              <ul className="grid gap-1.5">
                {active.map((at) => {
                  const live = positions[at.trip.id];
                  const seed = at.last_position;
                  const lat = live ? live.lat : seed ? Number(seed.lat) : null;
                  const lng = live ? live.lng : seed ? Number(seed.lng) : null;
                  const located = lat != null && lng != null;
                  const isSelected = selectedId === at.trip.id;
                  return (
                    <li key={at.trip.id}>
                      <button
                        type="button"
                        onClick={() => focusBus(at)}
                        aria-pressed={isSelected}
                        title="Show on map"
                        className={cn(
                          "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                          isSelected
                            ? "border-primary/50 bg-primary/5 ring-1 ring-primary/30"
                            : "bg-muted/30 hover:bg-muted",
                        )}
                      >
                        <span className="flex items-center gap-2 font-medium">
                          <MapPin
                            className={cn(
                              "size-3.5 shrink-0",
                              isSelected
                                ? "text-primary"
                                : located
                                  ? "text-emerald-500"
                                  : "text-muted-foreground",
                            )}
                          />
                          Bus {at.trip.bus_plate}
                        </span>
                        <span className="label-mono shrink-0 text-[0.6rem] text-muted-foreground">
                          {located ? `${lat.toFixed(5)}, ${lng.toFixed(5)}` : "waiting for fix"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Invisible subscription to one trip's live stream; reports updates to the parent. */
function TripFeed({
  tripId,
  onLocation,
  onCompleted,
}: {
  tripId: number;
  onLocation: (tripId: number, ev: LocationEvent) => void;
  onCompleted: (tripId: number) => void;
}) {
  const handle = useCallback(
    (data: unknown) => {
      const msg = parseServerMessage(data);
      if (!msg) return;
      if (isLocationEvent(msg) && Number(msg.trip_id) === tripId) {
        onLocation(tripId, msg);
      } else if (isTripCompleted(msg)) {
        onCompleted(tripId);
      }
    },
    [tripId, onLocation, onCompleted],
  );

  useSocket(`/ws/trip/${tripId}/`, { onEvent: handle });
  return null;
}
