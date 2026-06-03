"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Plus, Search, SquarePen } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDelete } from "@/components/confirm-delete";
import { CursorPager, DataTable } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminListDrivers, deleteDriver, type DriverListParams } from "@/lib/api/drivers";
import { toApiError } from "@/lib/api/error";
import { formatDate } from "@/lib/format";
import type { Driver } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { cn } from "@/lib/utils";

export default function AdminDriversPage() {
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "email", desc: false }]);
  const debouncedSearch = useDebouncedValue(search.trim());
  const ordering = sorting.length
    ? `${sorting[0].desc ? "-" : ""}${sorting[0].id}`
    : undefined;

  const params: DriverListParams = { search: debouncedSearch || undefined, ordering };
  const list = useCursorList<Driver, DriverListParams>({
    queryKey: QUERY_KEYS.adminDrivers(params),
    params,
    fetchPage: (args) => adminListDrivers(args),
  });

  const columns: ColumnDef<Driver, unknown>[] = [
    {
      id: "email",
      accessorKey: "email",
      header: "Email",
      enableSorting: true,
      cell: ({ row }) => <span className="font-medium">{row.original.email}</span>,
    },
    {
      id: "full_name",
      accessorKey: "full_name",
      header: "Name",
      enableSorting: false,
      cell: ({ row }) =>
        row.original.full_name || <span className="text-muted-foreground">—</span>,
    },
    {
      id: "phone",
      accessorKey: "phone",
      header: "Phone",
      enableSorting: false,
      cell: ({ row }) =>
        row.original.phone || <span className="text-muted-foreground">—</span>,
    },
    {
      id: "is_verified",
      header: "Verified",
      enableSorting: false,
      cell: ({ row }) => <VerifiedBadge verified={row.original.is_verified} />,
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
      cell: ({ row }) => <DriverRowActions driver={row.original} />,
    },
  ];

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Manage</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Drivers</h1>
        </div>
        <Button asChild>
          <Link href="/admin/drivers/new">
            <Plus className="size-4" />
            New driver
          </Link>
        </Button>
      </header>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by email, name, phone…"
          className="pl-9"
          aria-label="Search drivers"
        />
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
          emptyMessage="No drivers yet."
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

function VerifiedBadge({ verified }: { verified: boolean }) {
  return (
    <Badge
      className={cn(
        verified
          ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
          : "bg-muted text-muted-foreground",
      )}
    >
      {verified ? "Verified" : "Unverified"}
    </Badge>
  );
}

function DriverRowActions({ driver }: { driver: Driver }) {
  const queryClient = useQueryClient();
  const del = useMutation({
    mutationFn: () => deleteDriver(driver.id),
    onSuccess: () => {
      toast.success(`Deleted ${driver.email}.`);
      queryClient.invalidateQueries({ queryKey: ["admin", "drivers"] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.drivers });
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  return (
    <div className="flex items-center justify-end gap-0.5">
      <Button asChild variant="ghost" size="icon-sm" aria-label="Edit driver">
        <Link href={`/admin/drivers/${driver.id}/edit`}>
          <SquarePen className="size-4 text-muted-foreground" />
        </Link>
      </Button>
      <ConfirmDelete
        title={`Delete ${driver.email}?`}
        description="This soft-deletes the driver and disables their login. It can't be undone here."
        onConfirm={() => del.mutate()}
        disabled={del.isPending}
      />
    </div>
  );
}
