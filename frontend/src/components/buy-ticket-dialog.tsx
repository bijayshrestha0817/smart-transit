"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ticket as TicketIcon } from "lucide-react";
import { toast } from "sonner";

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
import { toApiError } from "@/lib/api/error";
import { listRoutes } from "@/lib/api/routes";
import { issueTicket } from "@/lib/api/tickets";
import { activeTrips } from "@/lib/api/trips";
import { getWalletBalance } from "@/lib/api/wallet";
import type { PaymentGateway } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";

const GATEWAYS: { value: PaymentGateway; label: string; soon: boolean }[] = [
  { value: "wallet", label: "Wallet (store credit)", soon: false },
  { value: "khalti", label: "Khalti", soon: true },
  { value: "esewa", label: "eSewa", soon: true },
  { value: "stripe", label: "Card · Stripe", soon: true },
];

export function BuyTicketButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [routeId, setRouteId] = useState("");
  const [tripId, setTripId] = useState("");
  const [gateway, setGateway] = useState<PaymentGateway>("wallet");

  const routesQuery = useQuery({
    queryKey: ["routes", "options"],
    queryFn: () => listRoutes({ page_size: 100, ordering: "name" }),
    enabled: open,
  });
  const tripsQuery = useQuery({
    queryKey: QUERY_KEYS.activeTrips(Number(routeId)),
    queryFn: () => activeTrips(Number(routeId)),
    enabled: open && Number(routeId) > 0,
  });
  const walletQuery = useQuery({
    queryKey: QUERY_KEYS.wallet,
    queryFn: getWalletBalance,
    enabled: open,
  });

  const reset = () => {
    setRouteId("");
    setTripId("");
    setGateway("wallet");
  };

  const mutation = useMutation({
    mutationFn: () => issueTicket({ trip: Number(tripId), gateway }),
    onSuccess: (ticket) => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.wallet });
      setOpen(false);
      reset();
      toast.success("Ticket purchased.");
      router.push(`/passenger/tickets/${ticket.id}`);
    },
    onError: (err) => {
      const e = toApiError(err);
      if (e.has("insufficient_balance"))
        toast.error("Your wallet balance is too low for this fare.");
      else if (e.has("gateway_not_configured"))
        toast.error("Online payments aren't available yet — pay with Wallet.");
      else if (e.has("invalid_trip")) toast.error("That trip isn't available anymore.");
      else toast.error(e.message);
    },
  });

  const routes = routesQuery.data?.rows ?? [];
  const selectedRoute = routes.find((r) => String(r.id) === routeId);
  const trips = (tripsQuery.data ?? []).map((a) => a.trip);
  const balance = Number(walletQuery.data?.balance ?? "0");
  // Fares are always > 0 (backend-enforced), so a 0 wallet balance can never cover one.
  const walletEmpty = gateway === "wallet" && walletQuery.isSuccess && balance <= 0;
  const ready = Number(routeId) > 0 && Number(tripId) > 0 && !walletEmpty;

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <TicketIcon className="size-4" />
        Buy a ticket
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Buy a ticket</DialogTitle>
            <DialogDescription>
              Pick a route and a bus that&apos;s running now, then pay. The fare is set by the
              route.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-1">
            <div className="grid gap-1.5">
              <Label>Route</Label>
              <Select
                value={routeId}
                onValueChange={(v) => {
                  setRouteId(v);
                  setTripId("");
                }}
              >
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
              {selectedRoute && (
                <p className="text-xs text-muted-foreground">
                  Fare:{" "}
                  <span className="font-medium text-foreground">
                    {formatMoney(selectedRoute.fare)}
                  </span>{" "}
                  per ride
                </p>
              )}
            </div>

            <div className="grid gap-1.5">
              <Label>Bus (running now)</Label>
              <Select value={tripId} onValueChange={setTripId} disabled={!routeId}>
                <SelectTrigger>
                  <SelectValue placeholder={routeId ? "Select a bus" : "Choose a route first"} />
                </SelectTrigger>
                <SelectContent>
                  {trips.map((t) => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      Bus {t.bus_plate}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {routeId && tripsQuery.isSuccess && trips.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No buses are running on this route right now.
                </p>
              )}
            </div>

            <div className="grid gap-1.5">
              <Label>Pay with</Label>
              <Select value={gateway} onValueChange={(v) => setGateway(v as PaymentGateway)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GATEWAYS.map((g) => (
                    <SelectItem key={g.value} value={g.value} disabled={g.soon}>
                      {g.label}
                      {g.soon ? " · coming soon" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {gateway === "wallet" && walletQuery.isSuccess && (
                <p className="text-xs text-muted-foreground">
                  Wallet balance:{" "}
                  <span className="font-medium text-foreground">{formatMoney(balance)}</span>
                </p>
              )}
              {walletEmpty ? (
                <p className="text-xs text-amber-600 dark:text-amber-500">
                  Your wallet has no credit yet — credit comes from refunding a ticket, and online
                  payment is coming soon.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Wallet credit comes from ticket refunds. Online gateways arrive later.
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => mutation.mutate()} disabled={!ready || mutation.isPending}>
              {mutation.isPending ? "Purchasing…" : "Buy ticket"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
