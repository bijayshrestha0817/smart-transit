"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Plus, Search, SquarePen } from "lucide-react";
import { toast } from "sonner";

import { ConfirmDelete } from "@/components/confirm-delete";
import { CursorPager, DataTable } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminListRoutes, deleteRoute, type RouteListParams } from "@/lib/api/routes";
import { toApiError } from "@/lib/api/error";
import { formatDate } from "@/lib/format";
import type { Route } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

export default function AdminRoutesPage() {
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "name", desc: false }]);
  const debouncedSearch = useDebouncedValue(search.trim());
  const ordering = sorting.length
    ? `${sorting[0].desc ? "-" : ""}${sorting[0].id}`
    : undefined;

  const params: RouteListParams = { search: debouncedSearch || undefined, ordering };
  const list = useCursorList<Route, RouteListParams>({
    queryKey: QUERY_KEYS.adminRoutes(params),
    params,
    fetchPage: (args) => adminListRoutes(args),
  });

  const columns: ColumnDef<Route, unknown>[] = [
    {
      id: "name",
      accessorKey: "name",
      header: "Name",
      enableSorting: true,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span
            className="size-3 shrink-0 rounded-full ring-1 ring-border"
            style={{ backgroundColor: row.original.color }}
          />
          <span className="font-medium">{row.original.name}</span>
        </div>
      ),
    },
    {
      id: "estimated_duration",
      accessorKey: "estimated_duration",
      header: "Duration",
      enableSorting: true,
      cell: ({ row }) => `~${row.original.estimated_duration} min`,
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
      cell: ({ row }) => <RouteRowActions route={row.original} />,
    },
  ];

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Manage</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Routes</h1>
        </div>
        <Button asChild>
          <Link href="/admin/routes/new">
            <Plus className="size-4" />
            New route
          </Link>
        </Button>
      </header>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search routes…"
          className="pl-9"
          aria-label="Search routes"
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
          emptyMessage="No routes yet."
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

function RouteRowActions({ route }: { route: Route }) {
  const queryClient = useQueryClient();
  const del = useMutation({
    mutationFn: () => deleteRoute(route.id),
    onSuccess: () => {
      toast.success(`Deleted “${route.name}”.`);
      queryClient.invalidateQueries({ queryKey: ["admin", "routes"] });
    },
    onError: (err) => toast.error(toApiError(err).message),
  });

  return (
    <div className="flex items-center justify-end gap-0.5">
      <Button asChild variant="ghost" size="icon-sm" aria-label="Edit route">
        <Link href={`/admin/routes/${route.id}/edit`}>
          <SquarePen className="size-4 text-muted-foreground" />
        </Link>
      </Button>
      <ConfirmDelete
        title={`Delete “${route.name}”?`}
        description="This soft-deletes the route and its stops. It won't appear in lists anymore."
        onConfirm={() => del.mutate()}
        disabled={del.isPending}
      />
    </div>
  );
}
