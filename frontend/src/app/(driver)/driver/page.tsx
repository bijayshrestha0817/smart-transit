"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, MapPinned, Navigation } from "lucide-react";

import { TripStatusBadge } from "@/components/trip-status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, toApiError } from "@/lib/api/error";
import { listDriverTrips } from "@/lib/api/trips";
import type { PaginationMeta, Trip } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";

type TripPage = { rows: Trip[]; pagination: PaginationMeta };

export default function DriverTripsPage() {
  const query = useQuery<TripPage, ApiError>({
    queryKey: QUERY_KEYS.driverTrips(),
    queryFn: () => listDriverTrips({ ordering: "-created_at" }),
  });

  const rows = query.data?.rows ?? [];
  const inProgress = rows.filter((t) => t.status === "in_progress");
  const scheduled = rows.filter((t) => t.status === "scheduled");
  const past = rows.filter((t) => t.status === "completed" || t.status === "cancelled");

  return (
    <div className="grid gap-6">
      <header>
        <p className="label-mono text-xs text-muted-foreground">Driver</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Your trips</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Start a scheduled trip to broadcast your location, or resume one in progress.
        </p>
      </header>

      {query.isError ? (
        <ErrorState message={toApiError(query.error).message} />
      ) : query.isLoading ? (
        <div className="grid gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-8">
          <TripSection title="In progress" trips={inProgress} cta="Resume" />
          <TripSection title="Scheduled" trips={scheduled} cta="Start" />
          <TripSection title="Past trips" trips={past} cta="View" muted />
        </div>
      )}
    </div>
  );
}

function TripSection({
  title,
  trips,
  cta,
  muted = false,
}: {
  title: string;
  trips: Trip[];
  cta: string;
  muted?: boolean;
}) {
  if (trips.length === 0) return null;
  return (
    <section className="grid gap-3">
      <h2 className="label-mono text-xs text-muted-foreground">
        {title} · {trips.length}
      </h2>
      <div className="grid gap-3">
        {trips.map((trip) => (
          <TripRow key={trip.id} trip={trip} cta={cta} muted={muted} />
        ))}
      </div>
    </section>
  );
}

function TripRow({ trip, cta, muted }: { trip: Trip; cta: string; muted: boolean }) {
  return (
    <Card className={muted ? "opacity-80" : undefined}>
      <CardContent className="flex items-center justify-between gap-4 py-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
            <Navigation className="size-4" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-medium">{trip.route_name}</p>
              <TripStatusBadge status={trip.status} />
            </div>
            <p className="label-mono mt-0.5 text-[0.6rem] text-muted-foreground">
              Bus {trip.bus_plate}
              {trip.passenger_count != null ? ` · ${trip.passenger_count} aboard` : ""}
            </p>
          </div>
        </div>
        <Button asChild variant={muted ? "outline" : "default"} size="sm">
          <Link href={`/driver/trips/${trip.id}`}>
            {cta}
            <ArrowRight className="size-3.5" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      <MapPinned className="size-5" />
      <p>No trips assigned yet. An operator will schedule trips for you.</p>
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
