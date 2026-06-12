"use client";

/**
 * Driver SOS control — the frontend producer for the admin alerts feed. Opens a confirm
 * dialog (SOS is high-consequence; guard against accidental taps), takes optional notes,
 * and POSTs `/driver/sos/`. On success the backend records a CRITICAL incident that lands
 * live on the operator's `/admin/alerts` feed.
 */

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { TriangleAlert } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { raiseSos } from "@/lib/api/driver-logs";
import { ApiError } from "@/lib/api/error";
import { cn } from "@/lib/utils";

export function DriverSosButton({
  tripId,
  className,
}: {
  tripId?: number;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");

  const sos = useMutation({
    mutationFn: () => raiseSos({ notes: notes.trim() || undefined, trip: tripId }),
    onSuccess: () => {
      toast.success("SOS sent — operators have been alerted.");
      setNotes("");
      setOpen(false);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Could not send SOS. Please try again."),
  });

  return (
    <AlertDialog open={open} onOpenChange={(o) => !sos.isPending && setOpen(o)}>
      <AlertDialogTrigger asChild>
        <Button size="lg" variant="destructive" className={cn("gap-2", className)}>
          <TriangleAlert className="size-4" />
          SOS
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Raise an emergency SOS?</AlertDialogTitle>
          <AlertDialogDescription>
            This immediately alerts operators with a critical incident. Use it for emergencies
            only.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="sos-notes">Notes (optional)</Label>
          <Textarea
            id="sos-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="What's happening? (e.g. breakdown at Kalanki)"
            rows={3}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={sos.isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault(); // keep the dialog open until the request resolves
              sos.mutate();
            }}
            disabled={sos.isPending}
            className="bg-destructive text-white hover:bg-destructive/90"
          >
            {sos.isPending ? "Sending…" : "Send SOS"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
