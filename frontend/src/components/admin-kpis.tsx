"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Map, Navigation, Ticket, TriangleAlert, Users, Wallet, Wrench } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchAdminKpis } from "@/lib/api/analytics";
import { ApiError, toApiError } from "@/lib/api/error";
import type { AdminKpis as AdminKpisData } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

type Tone = "default" | "positive" | "warn" | "danger";

const TONE: Record<Tone, { text: string; chip: string; dot: string }> = {
  default: { text: "text-foreground", chip: "bg-secondary text-secondary-foreground", dot: "bg-muted-foreground/40" },
  positive: {
    text: "text-emerald-600 dark:text-emerald-400",
    chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
  warn: {
    text: "text-amber-600 dark:text-amber-500",
    chip: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
    dot: "bg-amber-500",
  },
  danger: { text: "text-destructive", chip: "bg-destructive/10 text-destructive", dot: "bg-destructive" },
};

/** Admin operations KPIs, polled live. Renders on the operator console landing. */
export function AdminKpis() {
  const { data, isLoading, isError, error } = useQuery<AdminKpisData, ApiError>({
    queryKey: QUERY_KEYS.adminKpis,
    queryFn: fetchAdminKpis,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  if (isError) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 py-10 text-sm text-destructive">
        <TriangleAlert className="size-4" />
        {toApiError(error).message}
      </div>
    );
  }

  if (isLoading || !data) {
    return <KpisSkeleton />;
  }

  const k = data;
  const delay = k.avg_delay;
  const delayTone: Tone = delay == null ? "default" : delay <= 3 ? "positive" : delay <= 10 ? "warn" : "danger";

  return (
    <div className="grid gap-3.5">
      <SectionLabel>Operations snapshot</SectionLabel>

      {/* Headline KPIs — the four the operator scans first. */}
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Navigation}
          label="Active buses"
          value={String(k.active_buses)}
          sub="on a trip right now"
          tone={k.active_buses > 0 ? "positive" : "default"}
        />
        <StatCard
          icon={Ticket}
          label="Passengers today"
          value={String(k.passengers_today)}
          sub="tickets issued today"
        />
        <StatCard
          icon={Clock}
          label="Avg delay"
          value={delay == null ? "—" : `${delay.toFixed(1)} min`}
          sub={delay == null ? "no completed trips yet" : "across today's completed trips"}
          tone={delayTone}
        />
        <StatCard
          icon={Wallet}
          label="Revenue today"
          value={formatMoney(k.revenue)}
          sub="from successful payments"
        />
      </div>

      {/* Breakdowns. */}
      <div className="grid gap-3.5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span>Fleet status</span>
              <span className="label-mono text-[0.6rem] text-muted-foreground">{k.total_buses} buses</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-1.5">
            <div className="grid grid-cols-2 gap-1.5">
              <StatusLine label="Active" value={k.buses_active} tone="positive" />
              <StatusLine label="Idle" value={k.buses_idle} />
              <StatusLine label="Maintenance" value={k.buses_in_maintenance} tone={k.buses_in_maintenance > 0 ? "warn" : "default"} />
              <StatusLine label="Retired" value={k.buses_retired} />
            </div>
            <p className="px-1 pt-1 text-xs text-muted-foreground">
              {k.active_buses} {k.active_buses === 1 ? "bus is" : "buses are"} out on a trip now.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span>Trips today</span>
              <span className="label-mono text-[0.6rem] text-muted-foreground">{k.active_trips} active now</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-1.5">
            <div className="grid grid-cols-2 gap-1.5">
              <StatusLine label="Scheduled" value={k.scheduled_trips_today} />
              <StatusLine label="In progress" value={k.active_trips_today} tone={k.active_trips_today > 0 ? "positive" : "default"} />
              <StatusLine label="Completed" value={k.completed_trips_today} />
              <StatusLine label="Cancelled" value={k.cancelled_trips_today} tone={k.cancelled_trips_today > 0 ? "danger" : "default"} />
            </div>
            <p className="px-1 pt-1 text-xs text-muted-foreground">
              {k.completed_trips} trips completed all-time.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Operations strip. */}
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <MiniStat
          icon={TriangleAlert}
          label="Open alerts"
          value={String(k.open_alerts)}
          sub="SOS reported today"
          tone={k.open_alerts > 0 ? "danger" : "default"}
        />
        <MiniStat
          icon={Wrench}
          label="Maintenance due"
          value={String(k.maintenance_due)}
          sub="buses overdue for service"
          tone={k.maintenance_due > 0 ? "warn" : "default"}
        />
        <MiniStat icon={Map} label="Routes" value={String(k.total_routes)} sub="in the network" />
        <MiniStat
          icon={Users}
          label="Drivers"
          value={String(k.total_drivers)}
          sub={`${k.verified_drivers} verified`}
        />
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="relative flex size-2" aria-hidden>
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500/60" />
        <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
      </span>
      <p className="label-mono text-xs text-muted-foreground">{children}</p>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
}) {
  const t = TONE[tone];
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-5">
        <span className={cn("grid size-9 place-items-center rounded-lg", t.chip)}>
          <Icon className="size-4" />
        </span>
        <div>
          <p className="label-mono text-[0.65rem] text-muted-foreground">{label}</p>
          <p className={cn("mt-1 font-display text-3xl font-semibold tracking-tight tabular-nums", t.text)}>
            {value}
          </p>
          {sub ? <p className="mt-1 text-xs text-muted-foreground text-pretty">{sub}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusLine({ label, value, tone = "default" }: { label: string; value: number; tone?: Tone }) {
  const t = TONE[tone];
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-muted/40 px-3 py-2">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className={cn("size-1.5 rounded-full", t.dot)} aria-hidden />
        {label}
      </span>
      <span className="font-display text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function MiniStat({
  icon: Icon,
  label,
  value,
  sub,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
}) {
  const t = TONE[tone];
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", t.chip)}>
          <Icon className="size-4" />
        </span>
        <div className="min-w-0">
          <p className={cn("font-display text-xl font-semibold leading-none tabular-nums", t.text)}>{value}</p>
          <p className="label-mono mt-1 text-[0.6rem] text-muted-foreground">{label}</p>
          {sub ? <p className="truncate text-[0.7rem] text-muted-foreground">{sub}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function KpisSkeleton() {
  return (
    <div className="grid gap-3.5">
      <Skeleton className="h-4 w-40" />
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[7.5rem] rounded-xl" />
        ))}
      </div>
      <div className="grid gap-3.5 lg:grid-cols-2">
        <Skeleton className="h-44 rounded-xl" />
        <Skeleton className="h-44 rounded-xl" />
      </div>
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[4.5rem] rounded-xl" />
        ))}
      </div>
    </div>
  );
}
