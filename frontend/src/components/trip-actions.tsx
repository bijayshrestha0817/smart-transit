"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDelete } from "@/components/confirm-delete";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { adminListBuses } from "@/lib/api/buses";
import { listDriverOptions } from "@/lib/api/drivers";
import { toApiError } from "@/lib/api/error";
import { adminListRoutes } from "@/lib/api/routes";
import { createTrip, deleteTrip } from "@/lib/api/trips";
import type { Trip } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { adminTripSchema } from "@/lib/validation/trips";

const ADMIN_TRIPS_KEY = ["admin", "trips"];

/** "Schedule trip" button + controlled dialog (bus + route + driver). */
export function ScheduleTripButton() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [route, setRoute] = useState("");
  const [bus, setBus] = useState("");
  const [driver, setDriver] = useState("");

  // Options load only while the dialog is open.
  const routesQuery = useQuery({
    queryKey: ["admin", "routes", "options"],
    queryFn: () => adminListRoutes({ page_size: 100, ordering: "name" }),
    enabled: open,
  });
  const busesQuery = useQuery({
    queryKey: ["admin", "buses", "options"],
    queryFn: () => adminListBuses({ page_size: 100, ordering: "plate" }),
    enabled: open,
  });
  const driversQuery = useQuery({
    queryKey: QUERY_KEYS.drivers,
    queryFn: listDriverOptions,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () => createTrip({ bus: Number(bus), route: Number(route), driver: Number(driver) }),
    onSuccess: () => {
      toast.success("Trip scheduled.");
      void queryClient.invalidateQueries({ queryKey: ADMIN_TRIPS_KEY });
      reset();
      setOpen(false);
    },
    onError: (err) => {
      const e = toApiError(err);
      if (e.has("invalid_bus")) toast.error("Select an active bus.");
      else if (e.has("invalid_route")) toast.error("Select an active route.");
      else if (e.has("invalid_driver")) toast.error("Select an active driver.");
      else toast.error(e.message);
    },
  });

  const reset = () => {
    setRoute("");
    setBus("");
    setDriver("");
  };

  const routes = routesQuery.data?.rows ?? [];
  const buses = busesQuery.data?.rows ?? [];
  const drivers = driversQuery.data ?? [];
  // Gate submit on the same schema the payload must satisfy (positive int PKs).
  const ready = adminTripSchema.safeParse({ route, bus, driver }).success;

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        Schedule trip
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule a trip</DialogTitle>
            <DialogDescription>
              Assign a bus, route, and driver. The driver starts it from their portal.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-1">
            <div className="grid gap-1.5">
              <Label>Route</Label>
              <Select value={route} onValueChange={setRoute}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a route" />
                </SelectTrigger>
                <SelectContent>
                  {routes.map((r) => (
                    <SelectItem key={r.id} value={String(r.id)}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-1.5">
              <Label>Bus</Label>
              <Select value={bus} onValueChange={setBus}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a bus" />
                </SelectTrigger>
                <SelectContent>
                  {buses.map((b) => (
                    <SelectItem key={b.id} value={String(b.id)}>
                      {b.plate}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-1.5">
              <Label>Driver</Label>
              <Select value={driver} onValueChange={setDriver}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a driver" />
                </SelectTrigger>
                <SelectContent>
                  {drivers.map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>
                      {d.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {driversQuery.isSuccess && drivers.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No drivers yet — add one under Drivers first.
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => mutation.mutate()} disabled={!ready || mutation.isPending}>
              {mutation.isPending ? "Scheduling…" : "Schedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Per-row delete (soft) for the admin trips table. */
export function TripRowActions({ trip }: { trip: Trip }) {
  const queryClient = useQueryClient();
  const del = useMutation({
    mutationFn: () => deleteTrip(trip.id),
    onSuccess: () => {
      toast.success("Trip deleted.");
      void queryClient.invalidateQueries({ queryKey: ADMIN_TRIPS_KEY });
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  return (
    <div className="flex justify-end">
      <ConfirmDelete
        title={`Delete trip on ${trip.route_name}?`}
        description="This soft-deletes the scheduled trip. It won't appear in lists anymore."
        onConfirm={() => del.mutate()}
        disabled={del.isPending}
      />
    </div>
  );
}
