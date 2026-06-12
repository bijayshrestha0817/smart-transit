"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  MapPin,
  Navigation,
  Radio,
  Satellite,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { DriverSosButton } from "@/components/driver-sos-button";
import { LiveMap, type MapMarker } from "@/components/live-map";
import { TripStatusBadge } from "@/components/trip-status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useGeolocation } from "@/hooks/use-geolocation";
import { useSocket, type SocketStatus } from "@/hooks/use-socket";
import { ApiError, toApiError } from "@/lib/api/error";
import { endTrip, getDriverTrip, setPassengerCount, startTrip } from "@/lib/api/trips";
import type { Trip } from "@/lib/api/types";
import {
  isGpsError,
  isTripCompleted,
  outboundGpsSchema,
  parseServerMessage,
} from "@/lib/realtime/messages";
import { enqueueGps, flushGps, pendingCount } from "@/lib/realtime/gps-queue";
import { QUERY_KEYS } from "@/lib/queryClient";
import { passengerCountSchema } from "@/lib/validation/trips";
import { cn } from "@/lib/utils";

const CONN: Record<SocketStatus, { label: string; cls: string }> = {
  idle: { label: "Idle", cls: "bg-muted text-muted-foreground" },
  connecting: { label: "Connecting…", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500" },
  open: { label: "Live", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  closed: {
    label: "Reconnecting…",
    cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
  },
  forbidden: { label: "Disconnected", cls: "bg-destructive/10 text-destructive" },
};

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export default function DriverTripDetailPage() {
  const { id } = useParams<{ id: string }>();
  const tripId = Number(id);
  const valid = Number.isFinite(tripId) && tripId > 0;
  const queryClient = useQueryClient();

  const query = useQuery<Trip, ApiError>({
    queryKey: QUERY_KEYS.driverTrip(tripId),
    queryFn: () => getDriverTrip(tripId),
    enabled: valid,
  });
  const trip = query.data;
  const isInProgress = trip?.status === "in_progress";

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.driverTrip(tripId) });
    void queryClient.invalidateQueries({ queryKey: ["driver", "trips"] });
  }, [queryClient, tripId]);

  // ── Offline buffer counter ──
  const [pending, setPending] = useState(0);
  const refreshPending = useCallback(() => {
    void pendingCount(tripId).then(setPending).catch(() => {});
  }, [tripId]);
  useEffect(() => {
    if (valid) refreshPending();
  }, [valid, refreshPending]);

  // ── WebSocket (driver stream) ──
  const handleEvent = useCallback(
    (data: unknown) => {
      const msg = parseServerMessage(data);
      if (!msg) return;
      if (isTripCompleted(msg)) {
        toast.success("Trip completed.");
        invalidate();
      } else if (isGpsError(msg)) {
        // Server rejected a streamed point (the socket stays open) — warn softly so a
        // systematically bad GPS reading doesn't fail silently behind a "Live" badge.
        toast.warning("A location point was rejected by the server.");
      }
    },
    [invalidate],
  );
  const { status: wsStatus, lastError: wsError, send } = useSocket(`/ws/driver/${tripId}/`, {
    enabled: !!isInProgress,
    onEvent: handleEvent,
  });

  // ── Geolocation → stream (or buffer when offline) ──
  const { position, permission, error: geoError } = useGeolocation({ enabled: !!isInProgress });

  useEffect(() => {
    if (!isInProgress || !position) return;
    const latStr = position.lat.toFixed(6);
    const lngStr = position.lng.toFixed(6);
    const speedStr = Math.max(0, position.speed ?? 0).toFixed(2);
    const headingStr =
      position.heading != null && Number.isFinite(position.heading)
        ? position.heading.toFixed(2)
        : undefined;

    // Validate the rounded point against the outbound contract before it leaves the
    // device — a bad reading is dropped here rather than round-tripping to a server
    // `invalid_gps_point` rejection.
    const candidate = outboundGpsSchema.safeParse({
      lat: Number(latStr),
      lng: Number(lngStr),
      speed: Number(speedStr),
      ...(headingStr ? { heading: Number(headingStr) } : {}),
    });
    if (!candidate.success) return;

    const sent = send(candidate.data);

    if (!sent) {
      void enqueueGps(tripId, {
        lat: latStr,
        lng: lngStr,
        speed: speedStr,
        ...(headingStr ? { heading: headingStr } : {}),
        timestamp: new Date(position.timestamp).toISOString(),
      })
        .then(refreshPending)
        .catch(() => {});
    }
  }, [position, isInProgress, send, tripId, refreshPending]);

  // Flush the offline buffer (in order) whenever the socket (re)opens.
  useEffect(() => {
    if (wsStatus !== "open") return;
    void flushGps(tripId)
      .then((n) => {
        if (n > 0) toast.success(`Synced ${n} buffered point${n === 1 ? "" : "s"}.`);
      })
      .then(refreshPending)
      .catch(() => {});
  }, [wsStatus, tripId, refreshPending]);

  // ── Lifecycle mutations ──
  const startMutation = useMutation({
    mutationFn: () => startTrip(tripId),
    onSuccess: () => {
      toast.success("Trip started — broadcasting your location.");
      invalidate();
    },
    onError: (err) => {
      const e = toApiError(err);
      if (e.has("trip_already_started")) toast.error("This trip has already started.");
      else if (e.has("trip_not_assigned")) toast.error("This isn't your assigned trip.");
      else toast.error(e.message);
    },
  });

  const endMutation = useMutation({
    mutationFn: () => endTrip(tripId),
    onSuccess: () => {
      toast.success("Trip ended.");
      invalidate();
    },
    onError: (err) => {
      const e = toApiError(err);
      if (e.has("trip_not_in_progress")) toast.error("This trip isn't in progress.");
      else if (e.has("trip_not_assigned")) toast.error("This isn't your assigned trip.");
      else toast.error(e.message);
    },
  });

  const markers: MapMarker[] = position
    ? [
        {
          id: tripId,
          lat: position.lat,
          lng: position.lng,
          heading: position.heading,
          label: trip ? `Bus ${trip.bus_plate}` : undefined,
          color: "#10b981",
        },
      ]
    : [];

  return (
    <div className="grid gap-6">
      <Link
        href="/driver"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        All trips
      </Link>

      {!valid || query.isError ? (
        <DetailError error={query.error} invalid={!valid} />
      ) : query.isLoading || !trip ? (
        <DetailSkeleton />
      ) : (
        <>
          <header className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="font-display text-3xl font-semibold tracking-tight">
                  {trip.route_name}
                </h1>
                <TripStatusBadge status={trip.status} />
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Bus {trip.bus_plate}</p>
            </div>
            <div className="flex gap-2">
              {trip.status === "scheduled" && (
                <Button
                  size="lg"
                  onClick={() => startMutation.mutate()}
                  disabled={startMutation.isPending}
                >
                  <Navigation className="size-4" />
                  {startMutation.isPending ? "Starting…" : "Start trip"}
                </Button>
              )}
              {trip.status === "in_progress" && (
                <>
                  <DriverSosButton tripId={trip.id} />
                  <Button
                    size="lg"
                    variant="destructive"
                    onClick={() => endMutation.mutate()}
                    disabled={endMutation.isPending}
                  >
                    {endMutation.isPending ? "Ending…" : "End trip"}
                  </Button>
                </>
              )}
            </div>
          </header>

          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <div className="grid gap-6">
              {isInProgress && (
                <BroadcastCard
                  wsStatus={wsStatus}
                  wsError={wsError}
                  permission={permission}
                  geoError={geoError}
                  pending={pending}
                  position={position ? { lat: position.lat, lng: position.lng } : null}
                />
              )}

              <Card className="overflow-hidden p-0">
                <LiveMap markers={markers} className="h-[360px] w-full" />
              </Card>
            </div>

            <div className="grid gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Trip</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 text-sm">
                  <DetailRow label="Route" value={trip.route_name} />
                  <DetailRow label="Bus" value={trip.bus_plate} />
                  <DetailRow label="Driver" value={trip.driver_email} />
                  <DetailRow
                    label="Passengers"
                    value={trip.passenger_count != null ? String(trip.passenger_count) : "—"}
                  />
                  <DetailRow label="Started" value={formatTime(trip.start_time)} />
                  <DetailRow label="Ended" value={formatTime(trip.end_time)} />
                </CardContent>
              </Card>

              {isInProgress && (
                <PassengerCountControl
                  tripId={tripId}
                  current={trip.passenger_count}
                  onSaved={invalidate}
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BroadcastCard({
  wsStatus,
  wsError,
  permission,
  geoError,
  pending,
  position,
}: {
  wsStatus: SocketStatus;
  wsError: string | null;
  permission: string;
  geoError: string | null;
  pending: number;
  position: { lat: number; lng: number } | null;
}) {
  const conn = CONN[wsStatus];
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <Radio className="size-4 text-emerald-600 dark:text-emerald-400" />
          Broadcasting
        </CardTitle>
        <Badge className={cn(conn.cls)}>{conn.label}</Badge>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Satellite className="size-4" />
          {permission === "denied" ? (
            <span className="text-destructive">
              Location permission denied — enable it to broadcast.
            </span>
          ) : permission === "unsupported" ? (
            <span className="text-destructive">Location isn&apos;t available on this device.</span>
          ) : position ? (
            <span className="label-mono text-[0.7rem]">
              {position.lat.toFixed(5)}, {position.lng.toFixed(5)}
            </span>
          ) : (
            <span>Acquiring GPS fix…</span>
          )}
        </div>

        {pending > 0 && (
          <p className="text-xs text-amber-600 dark:text-amber-500">
            {pending} point{pending === 1 ? "" : "s"} buffered offline — will sync on reconnect.
          </p>
        )}
        {geoError && permission !== "denied" && (
          <p className="text-xs text-muted-foreground">{geoError}</p>
        )}
        {wsError && <p className="text-xs text-muted-foreground">{wsError}</p>}
      </CardContent>
    </Card>
  );
}

function PassengerCountControl({
  tripId,
  current,
  onSaved,
}: {
  tripId: number;
  current: number | null;
  onSaved: () => void;
}) {
  const [value, setValue] = useState(current != null ? String(current) : "");

  const mutation = useMutation({
    mutationFn: () => setPassengerCount(tripId, Number(value)),
    onSuccess: () => {
      toast.success("Passenger count updated.");
      onSaved();
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  const invalid = value === "" || !passengerCountSchema.safeParse({ count: value }).success;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="size-4" />
          Passengers aboard
        </CardTitle>
      </CardHeader>
      <CardContent className="flex items-end gap-2">
        <div className="grid flex-1 gap-1.5">
          <Label htmlFor="passenger-count">Current count</Label>
          <Input
            id="passenger-count"
            inputMode="numeric"
            value={value}
            onChange={(e) => setValue(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="0"
          />
        </div>
        <Button onClick={() => mutation.mutate()} disabled={invalid || mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Update"}
        </Button>
      </CardContent>
    </Card>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-right font-medium">{value}</span>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="grid gap-6">
      <Skeleton className="h-9 w-72" />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Skeleton className="h-[360px] rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
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
          <p>Trip not found, or not assigned to you.</p>
        </>
      ) : (
        <>
          <AlertCircle className="size-5 text-destructive" />
          <p>{error ? toApiError(error).message : "Could not load this trip."}</p>
        </>
      )}
    </div>
  );
}
