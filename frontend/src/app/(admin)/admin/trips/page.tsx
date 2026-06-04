"use client";

import { useState } from "react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Search } from "lucide-react";

import { CursorPager, DataTable } from "@/components/data-table";
import { ScheduleTripButton, TripRowActions } from "@/components/trip-actions";
import { TripStatusBadge } from "@/components/trip-status-badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { toApiError } from "@/lib/api/error";
import { adminListTrips, type AdminTripListParams } from "@/lib/api/trips";
import type { Trip, TripStatus } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";
import { TRIP_STATUSES } from "@/lib/validation/trips";

const ALL_STATUSES = "all";

export default function AdminTripsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(ALL_STATUSES);
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const debouncedSearch = useDebouncedValue(search.trim());
  const ordering = sorting.length ? `${sorting[0].desc ? "-" : ""}${sorting[0].id}` : undefined;

  const params: AdminTripListParams = {
    search: debouncedSearch || undefined,
    status: statusFilter === ALL_STATUSES ? undefined : (statusFilter as TripStatus),
    ordering,
  };
  const list = useCursorList<Trip, AdminTripListParams>({
    queryKey: QUERY_KEYS.adminTrips(params),
    params,
    fetchPage: (args) => adminListTrips(args),
  });

  const columns: ColumnDef<Trip, unknown>[] = [
    {
      id: "route",
      header: "Route",
      enableSorting: false,
      cell: ({ row }) => <span className="font-medium">{row.original.route_name}</span>,
    },
    { id: "bus", header: "Bus", enableSorting: false, cell: ({ row }) => row.original.bus_plate },
    {
      id: "driver",
      header: "Driver",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-muted-foreground">{row.original.driver_email}</span>
      ),
    },
    {
      id: "status",
      accessorKey: "status",
      header: "Status",
      enableSorting: true,
      cell: ({ row }) => <TripStatusBadge status={row.original.status} />,
    },
    {
      id: "passengers",
      header: "Pax",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.passenger_count ?? "—"}
        </span>
      ),
    },
    {
      id: "created_at",
      accessorKey: "created_at",
      header: "Created",
      enableSorting: true,
      cell: ({ row }) => (
        <span className="text-muted-foreground">{formatDate(row.original.created_at)}</span>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      enableSorting: false,
      cell: ({ row }) => <TripRowActions trip={row.original} />,
    },
  ];

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Manage</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Trips</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Schedule trips for drivers to run. Watch them live under Fleet.
          </p>
        </div>
        <ScheduleTripButton />
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by plate, route, or driver…"
            className="pl-9"
            aria-label="Search trips"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="capitalize sm:w-44" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>All statuses</SelectItem>
            {TRIP_STATUSES.map((s) => (
              <SelectItem key={s} value={s} className="capitalize">
                {s.replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isError ? (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 py-10 text-center text-sm text-destructive">
          {toApiError(list.error).message}
        </p>
      ) : (
        <DataTable
          columns={columns}
          data={list.rows}
          isLoading={list.isLoading}
          sorting={sorting}
          onSortingChange={setSorting}
          emptyMessage="No trips scheduled yet."
        />
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
