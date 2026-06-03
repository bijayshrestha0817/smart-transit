"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, Search } from "lucide-react";

import { CursorPager } from "@/components/data-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { listRoutes, type RouteListParams } from "@/lib/api/routes";
import { toApiError } from "@/lib/api/error";
import type { Route } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

const ORDERINGS = [
  { value: "name", label: "Name (A–Z)" },
  { value: "-created_at", label: "Newest" },
  { value: "estimated_duration", label: "Shortest first" },
] as const;

export default function PassengerRoutesPage() {
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState<string>("name");
  const debouncedSearch = useDebouncedValue(search.trim());

  const params: RouteListParams = {
    search: debouncedSearch || undefined,
    ordering,
  };
  const list = useCursorList<Route, RouteListParams>({
    queryKey: QUERY_KEYS.routes(params),
    params,
    fetchPage: (args) => listRoutes(args),
  });

  return (
    <div className="grid gap-6">
      <header>
        <p className="label-mono text-xs text-muted-foreground">Browse</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Routes</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Every line in the network. Open a route to see its stops in order.
        </p>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search routes by name…"
            className="pl-9"
            aria-label="Search routes"
          />
        </div>
        <Select value={ordering} onValueChange={setOrdering}>
          <SelectTrigger className="sm:w-48" aria-label="Sort routes">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ORDERINGS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isError ? (
        <ErrorState message={toApiError(list.error).message} />
      ) : list.isLoading ? (
        <CardGrid>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </CardGrid>
      ) : list.rows.length === 0 ? (
        <EmptyState />
      ) : (
        <CardGrid>
          {list.rows.map((route) => (
            <RouteCard key={route.id} route={route} />
          ))}
        </CardGrid>
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

function CardGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function RouteCard({ route }: { route: Route }) {
  return (
    <Link href={`/passenger/routes/${route.id}`} className="group">
      <Card className="h-full transition-colors group-hover:border-foreground/20 group-hover:bg-muted/30">
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span
              className="size-3.5 shrink-0 rounded-full ring-1 ring-border"
              style={{ backgroundColor: route.color }}
              aria-hidden
            />
            <CardTitle className="truncate text-base">{route.name}</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            ~{route.estimated_duration} min end to end
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      No routes found.
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
