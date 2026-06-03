"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SquarePen, UserCog, Wrench } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDelete } from "@/components/confirm-delete";
import { Badge } from "@/components/ui/badge";
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
import { Textarea } from "@/components/ui/textarea";
import { assignDriver, deleteBus, markMaintenance } from "@/lib/api/buses";
import { toApiError } from "@/lib/api/error";
import type { Bus, BusStatus, Driver } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<BusStatus, string> = {
  active: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  idle: "bg-muted text-muted-foreground",
  maintenance: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
  retired: "bg-destructive/10 text-destructive",
};

export function StatusBadge({ status }: { status: BusStatus }) {
  return <Badge className={cn("capitalize", STATUS_STYLES[status])}>{status}</Badge>;
}

export function BusRowActions({ bus, drivers }: { bus: Bus; drivers: Driver[] }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "buses"] });
  const [assignOpen, setAssignOpen] = useState(false);
  const [maintOpen, setMaintOpen] = useState(false);

  const del = useMutation({
    mutationFn: () => deleteBus(bus.id),
    onSuccess: () => {
      toast.success(`Deleted ${bus.plate}.`);
      invalidate();
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  return (
    <div className="flex items-center justify-end gap-0.5">
      <Button asChild variant="ghost" size="icon-sm" aria-label="Edit bus">
        <Link href={`/admin/buses/${bus.id}/edit`}>
          <SquarePen className="size-4 text-muted-foreground" />
        </Link>
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Assign driver"
        onClick={() => setAssignOpen(true)}
      >
        <UserCog className="size-4 text-muted-foreground" />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Mark for maintenance"
        onClick={() => setMaintOpen(true)}
      >
        <Wrench className="size-4 text-muted-foreground" />
      </Button>
      <ConfirmDelete
        title={`Delete ${bus.plate}?`}
        description="This soft-deletes the bus. It won't appear in lists anymore."
        onConfirm={() => del.mutate()}
        disabled={del.isPending}
      />

      <AssignDriverDialog
        bus={bus}
        drivers={drivers}
        open={assignOpen}
        onOpenChange={setAssignOpen}
        onDone={invalidate}
      />
      <MaintenanceDialog
        bus={bus}
        open={maintOpen}
        onOpenChange={setMaintOpen}
        onDone={invalidate}
      />
    </div>
  );
}

function AssignDriverDialog({
  bus,
  drivers,
  open,
  onOpenChange,
  onDone,
}: {
  bus: Bus;
  drivers: Driver[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [driverId, setDriverId] = useState(bus.assigned_driver ? String(bus.assigned_driver) : "");

  const mutation = useMutation({
    mutationFn: () => assignDriver(bus.id, Number(driverId)),
    onSuccess: () => {
      toast.success("Driver assigned.");
      onDone();
      onOpenChange(false);
    },
    onError: (err) => {
      const apiError = toApiError(err);
      toast.error(apiError.has("invalid_driver") ? "Select an active driver." : apiError.message);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign driver</DialogTitle>
          <DialogDescription>Bus {bus.plate}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label>Driver</Label>
          <Select value={driverId} onValueChange={setDriverId}>
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
          {drivers.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No drivers yet — add one under Drivers first.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!driverId || mutation.isPending}>
            {mutation.isPending ? "Assigning…" : "Assign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MaintenanceDialog({
  bus,
  open,
  onOpenChange,
  onDone,
}: {
  bus: Bus;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () => markMaintenance(bus.id, note.trim() || undefined),
    onSuccess: () => {
      toast.success(`${bus.plate} marked for maintenance.`);
      onDone();
      onOpenChange(false);
      setNote("");
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mark for maintenance</DialogTitle>
          <DialogDescription>
            Sets {bus.plate} to maintenance status. The note is for your reference only — it
            isn&apos;t stored.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="maintenance-note">Note (optional)</Label>
          <Textarea
            id="maintenance-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What's being serviced?"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Mark maintenance"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
