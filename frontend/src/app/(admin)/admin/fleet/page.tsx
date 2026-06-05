"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Bus, MapPin, Radio } from "lucide-react";

import { LiveMap, type MapMarker } from "@/components/live-map";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSocket, type SocketStatus } from "@/hooks/use-socket";
import { ApiError, toApiError } from "@/lib/api/error";
import { fleetSnapshot } from "@/lib/api/trips";
import type { ActiveTrip } from "@/lib/api/types";
import { isLocationEvent, parseServerMessage } from "@/lib/realtime/messages";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

const CONN: Record<SocketStatus, { label: string; cls: string }> = {
  idle: { label: "Idle", cls: "bg-muted text-muted-foreground" },
  connecting: { label: "Connecting…", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500" },
  open: { label: "Live", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  closed: { label: "Reconnecting…", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500" },
  forbidden: { label: "Disconnected", cls: "bg-destructive/10 text-destructive" },
};

interface LivePos {
  lat: number;
  lng: number;
  heading: number | null;
  ts: string;
}

function formatClock(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString();
}

export default function AdminFleetPage() {
  // Refetch the snapshot periodically so trips that ended (no lifecycle events on the
  // fleet socket) drop off the map.
  const query = useQuery<ActiveTrip[], ApiError>({
    queryKey: QUERY_KEYS.fleet,
    queryFn: fleetSnapshot,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const [positions, setPositions] = useState<Record<number, LivePos>>({});
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [focus, setFocus] = useState<{ lat: number; lng: number; nonce: number } | null>(null);

  // One fleet socket carries every active trip's location events (keyed by trip_id).
  const handle = useCallback((data: unknown) => {
    const msg = parseServerMessage(data);
    if (msg && isLocationEvent(msg)) {
      const tid = Number(msg.trip_id);
      setPositions((prev) => ({
        ...prev,
        [tid]: {
          lat: Number(msg.lat),
          lng: Number(msg.lng),
          heading: msg.heading != null ? Number(msg.heading) : null,
          ts: msg.ts,
        },
      }));
    }
  }, []);
  const { status: wsStatus } = useSocket("/ws/fleet/", { onEvent: handle });

  const active = query.data ?? [];

  // Keep the live-position cache bounded to currently-active trips (the fleet socket has
  // no lifecycle events, so ended trips are only known via the snapshot refetch). Trip ids
  // are DB PKs and never reused, so dropping stale ids is safe.
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
        label: `Bus ${at.trip.bus_plate} · ${at.trip.route_name}`,
        color: "#1e88e5",
      };
    })
    .filter((m): m is MapMarker => m !== null);

  // Select a bus from the list → highlight it + fly the map to its current position.
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

  const conn = CONN[wsStatus];

  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Operations</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Live fleet</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Every in-progress trip, tracked in real time.
          </p>
        </div>
        <Badge className={cn("gap-1.5", conn.cls)}>
          <Radio className="size-3" />
          {conn.label}
        </Badge>
      </header>

      {query.isError ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 py-12 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {toApiError(query.error).message}
        </div>
      ) : query.isLoading ? (
        <Skeleton className="h-[480px] w-full rounded-xl" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Card className="overflow-hidden p-0">
            <LiveMap
              markers={markers}
              focus={focus}
              selectedId={selectedId}
              className="h-[480px] w-full"
            />
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                <span>Active buses</span>
                <span className="label-mono text-[0.6rem] text-muted-foreground">
                  {active.length}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {active.length === 0 ? (
                <p className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
                  <Bus className="size-5" />
                  No trips are in progress right now.
                </p>
              ) : (
                <ul className="grid gap-1.5">
                  {active.map((at) => {
                    const live = positions[at.trip.id];
                    const hasLoc = Boolean(live || at.last_position);
                    const isSelected = selectedId === at.trip.id;
                    return (
                      <li key={at.trip.id}>
                        <button
                          type="button"
                          onClick={() => focusBus(at)}
                          aria-pressed={isSelected}
                          title="Show on map"
                          className={cn(
                            "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left transition-colors",
                            isSelected
                              ? "border-primary/50 bg-primary/5 ring-1 ring-primary/30"
                              : "bg-muted/30 hover:bg-muted",
                          )}
                        >
                          <div className="min-w-0">
                            <p className="flex items-center gap-1.5 truncate text-sm font-medium">
                              <MapPin
                                className={cn(
                                  "size-3.5 shrink-0",
                                  isSelected ? "text-primary" : "text-muted-foreground",
                                )}
                              />
                              {at.trip.bus_plate}
                            </p>
                            <p className="label-mono truncate pl-5 text-[0.6rem] text-muted-foreground">
                              {at.trip.route_name}
                            </p>
                          </div>
                          <span className="label-mono shrink-0 text-[0.6rem] text-muted-foreground">
                            {hasLoc ? formatClock(live?.ts ?? at.last_position?.timestamp) : "no fix"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
