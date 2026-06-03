"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Plus, Search } from "lucide-react";

import { BusRowActions, StatusBadge } from "@/components/bus-row-actions";
import { CursorPager, DataTable } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { adminListBuses, type BusListParams } from "@/lib/api/buses";
import { listDriverOptions } from "@/lib/api/drivers";
import { toApiError } from "@/lib/api/error";
import { formatDate } from "@/lib/format";
import type { Bus, BusStatus } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { BUS_STATUSES } from "@/lib/validation/buses";

const ALL_STATUSES = "all";

export default function AdminBusesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(ALL_STATUSES);
  const [sorting, setSorting] = useState<SortingState>([{ id: "plate", desc: false }]);
  const debouncedSearch = useDebouncedValue(search.trim());
  const ordering = sorting.length
    ? `${sorting[0].desc ? "-" : ""}${sorting[0].id}`
    : undefined;

  const driversQuery = useQuery({
    queryKey: QUERY_KEYS.drivers,
    queryFn: listDriverOptions,
  });
  const drivers = driversQuery.data ?? [];

  const params: BusListParams = {
    search: debouncedSearch || undefined,
    status: statusFilter === ALL_STATUSES ? undefined : (statusFilter as BusStatus),
    ordering,
  };
  const list = useCursorList<Bus, BusListParams>({
    queryKey: QUERY_KEYS.adminBuses(params),
    params,
    fetchPage: (args) => adminListBuses(args),
  });

  const columns: ColumnDef<Bus, unknown>[] = [
    {
      id: "plate",
      accessorKey: "plate",
      header: "Plate",
      enableSorting: true,
      cell: ({ row }) => <span className="font-medium">{row.original.plate}</span>,
    },
    { id: "capacity", accessorKey: "capacity", header: "Capacity", enableSorting: false },
    {
      id: "status",
      accessorKey: "status",
      header: "Status",
      enableSorting: true,
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      id: "driver",
      header: "Driver",
      enableSorting: false,
      cell: ({ row }) => (
        <span className={row.original.assigned_driver_email ? "" : "text-muted-foreground"}>
          {row.original.assigned_driver_email ?? "—"}
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
      cell: ({ row }) => <BusRowActions bus={row.original} drivers={drivers} />,
    },
  ];

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Manage</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Buses</h1>
        </div>
        <Button asChild>
          <Link href="/admin/buses/new">
            <Plus className="size-4" />
            New bus
          </Link>
        </Button>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by plate…"
            className="pl-9"
            aria-label="Search buses"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="capitalize sm:w-44" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>All statuses</SelectItem>
            {BUS_STATUSES.map((s) => (
              <SelectItem key={s} value={s} className="capitalize">
                {s}
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
          emptyMessage="No buses yet."
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
