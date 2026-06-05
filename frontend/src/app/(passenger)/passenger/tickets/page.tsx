"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, Ticket as TicketIcon, Wallet } from "lucide-react";

import { BuyTicketButton } from "@/components/buy-ticket-dialog";
import { CursorPager } from "@/components/data-table";
import { PaymentStatusBadge, TicketStatusBadge } from "@/components/ticket-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCursorList } from "@/hooks/use-cursor-list";
import { toApiError } from "@/lib/api/error";
import { listTickets, type TicketListParams } from "@/lib/api/tickets";
import type { Ticket, TicketStatus } from "@/lib/api/types";
import { formatDate, formatMoney } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";

const ALL = "all";
const STATUSES: TicketStatus[] = [
  "issued",
  "active",
  "used",
  "expired",
  "refunded",
  "cancelled",
];

export default function PassengerTicketsPage() {
  const [statusFilter, setStatusFilter] = useState<string>(ALL);

  const params: TicketListParams = {
    status: statusFilter === ALL ? undefined : (statusFilter as TicketStatus),
    ordering: "-created_at",
  };
  const list = useCursorList<Ticket, TicketListParams>({
    queryKey: QUERY_KEYS.tickets(params),
    params,
    fetchPage: (args) => listTickets(args),
  });

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Passenger</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Tickets</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your rides and QR codes. Refunds return store credit to your wallet.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <BuyTicketButton />
          <Button asChild variant="ghost" size="sm">
            <Link href="/passenger/wallet">
              <Wallet className="size-4" />
              Wallet
            </Link>
          </Button>
        </div>
      </header>

      <div className="flex">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="capitalize sm:w-48" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All tickets</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s} className="capitalize">
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isError ? (
        <ErrorState message={toApiError(list.error).message} />
      ) : list.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : list.rows.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {list.rows.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} />
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

function TicketCard({ ticket }: { ticket: Ticket }) {
  return (
    <Link href={`/passenger/tickets/${ticket.id}`} className="group">
      <Card className="h-full transition-colors group-hover:border-foreground/20 group-hover:bg-muted/30">
        <CardContent className="grid gap-3 py-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate font-medium">{ticket.route_name}</p>
              <p className="label-mono mt-0.5 text-[0.6rem] text-muted-foreground">
                {formatDate(ticket.created_at)} · {formatMoney(ticket.fare)}
              </p>
            </div>
            <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <TicketStatusBadge status={ticket.status} />
            <PaymentStatusBadge status={ticket.payment_status} />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      <TicketIcon className="size-5" />
      <p>No tickets yet. Buy one for a bus that&apos;s running.</p>
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
