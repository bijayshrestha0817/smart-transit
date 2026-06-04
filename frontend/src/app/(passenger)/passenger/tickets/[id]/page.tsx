"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { AlertCircle, ArrowLeft, RotateCcw, Ticket as TicketIcon } from "lucide-react";
import { toast } from "sonner";

import { PaymentStatusBadge, TicketStatusBadge } from "@/components/ticket-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, toApiError } from "@/lib/api/error";
import { getTicket, refundTicket } from "@/lib/api/tickets";
import type { Ticket } from "@/lib/api/types";
import { formatDateTime, formatMoney } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const ticketId = Number(id);
  const valid = Number.isFinite(ticketId) && ticketId > 0;
  const queryClient = useQueryClient();

  const query = useQuery<Ticket, ApiError>({
    queryKey: QUERY_KEYS.ticket(ticketId),
    queryFn: () => getTicket(ticketId),
    enabled: valid,
  });
  const ticket = query.data;

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ticket(ticketId) });
    void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    void queryClient.invalidateQueries({ queryKey: QUERY_KEYS.wallet });
  };

  const [confirming, setConfirming] = useState(false);

  const refund = useMutation({
    mutationFn: () => refundTicket(ticketId),
    onSuccess: () => {
      toast.success("Refunded to your wallet.");
      setConfirming(false);
      invalidate();
    },
    onError: (err) => {
      const e = toApiError(err);
      setConfirming(false);
      if (e.has("ticket_not_refundable")) toast.error("This ticket can't be refunded.");
      else toast.error(e.message);
    },
  });

  const refundable = ticket?.payment_status === "success";
  // A pending non-wallet payment is awaiting an online gateway that isn't live yet (D4),
  // so there is no completable action — we surface an honest "coming soon" note instead.
  const pendingExternal = ticket?.payment_status === "pending" && ticket.gateway !== "wallet";
  const qrActive = ticket && (ticket.status === "active" || ticket.status === "issued");

  return (
    <div className="grid gap-6">
      <Link
        href="/passenger/tickets"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        All tickets
      </Link>

      {!valid || query.isError ? (
        <DetailError error={query.error} invalid={!valid} />
      ) : query.isLoading || !ticket ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Boarding pass</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-4 py-2">
              <div
                className={qrActive ? "" : "opacity-30 grayscale"}
                aria-label="Ticket QR code"
              >
                <div className="rounded-xl border bg-white p-4">
                  <QRCodeSVG value={ticket.qr_code} size={200} level="M" />
                </div>
              </div>
              <p className="text-center text-sm text-muted-foreground">
                {qrActive
                  ? "Show this QR to board."
                  : `This ticket is ${ticket.status} — the code is inactive.`}
              </p>
            </CardContent>
          </Card>

          <div className="grid content-start gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2 text-base">
                  <span className="truncate">{ticket.route_name}</span>
                  <TicketStatusBadge status={ticket.status} />
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <Row label="Fare" value={formatMoney(ticket.fare)} />
                <Row label="Ticket" value={`#${ticket.id}`} />
                <Row label="Purchased" value={formatDateTime(ticket.created_at)} />
                <div className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">Payment</span>
                  <span className="flex items-center gap-2">
                    <span className="capitalize">{ticket.gateway}</span>
                    <PaymentStatusBadge status={ticket.payment_status} />
                  </span>
                </div>
              </CardContent>
            </Card>

            {(refundable || pendingExternal) && (
              <Card>
                <CardContent className="flex flex-col gap-2 py-4">
                  {pendingExternal && (
                    <p className="rounded-lg border border-dashed px-3 py-2.5 text-sm text-muted-foreground">
                      Awaiting payment — online checkout for{" "}
                      <span className="capitalize">{ticket.gateway}</span> is coming soon.
                    </p>
                  )}
                  {refundable && (
                    <Button
                      variant={confirming ? "destructive" : "outline"}
                      onClick={() => (confirming ? refund.mutate() : setConfirming(true))}
                      disabled={refund.isPending}
                    >
                      <RotateCcw className="size-4" />
                      {refund.isPending
                        ? "Refunding…"
                        : confirming
                          ? "Confirm refund to wallet"
                          : "Refund to wallet"}
                    </Button>
                  )}
                  {refundable && confirming && (
                    <button
                      type="button"
                      className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setConfirming(false)}
                    >
                      Cancel
                    </button>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function DetailError({ error, invalid }: { error: ApiError | null; invalid: boolean }) {
  const notFound = invalid || (error ? toApiError(error).status === 404 : false);
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      {notFound ? (
        <>
          <TicketIcon className="size-5" />
          <p>Ticket not found.</p>
        </>
      ) : (
        <>
          <AlertCircle className="size-5 text-destructive" />
          <p>{error ? toApiError(error).message : "Could not load this ticket."}</p>
        </>
      )}
    </div>
  );
}
