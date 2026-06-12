"use client";

/**
 * Admin alerts feed — the operations incident log. Seeds the cursor-paginated history from
 * `GET /admin/alerts/`, then subscribes to `/ws/alerts/`: every live incident refetches the
 * authoritative feed (same pattern as the notification bell) and a CRITICAL one also raises a
 * toast so an operator notices without staring at the list. Acknowledge clears an open incident.
 */

import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertCircle, Check, Radio, ShieldAlert } from "lucide-react";

import { AlertSeverityBadge } from "@/components/alert-severity-badge";
import { CursorPager } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { acknowledgeAlert, listAlerts, type AlertListParams } from "@/lib/api/alerts";
import { ApiError } from "@/lib/api/error";
import type { Alert } from "@/lib/api/types";
import { relativeTime } from "@/lib/notifications-format";
import { parseAlertEvent } from "@/lib/realtime/messages";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useSocket, type SocketStatus } from "@/hooks/use-socket";
import { cn } from "@/lib/utils";

const CONN: Record<SocketStatus, { label: string; cls: string }> = {
  idle: { label: "Idle", cls: "bg-muted text-muted-foreground" },
  connecting: { label: "Connecting…", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500" },
  open: { label: "Live", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  closed: { label: "Reconnecting…", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-500" },
  forbidden: { label: "Disconnected", cls: "bg-destructive/10 text-destructive" },
};

const TYPE_LABEL: Record<string, string> = {
  sos: "SOS",
  overspeed: "Overspeed",
  route_deviation: "Route deviation",
  maintenance_due: "Maintenance due",
};

function describeTarget(a: Alert): string | null {
  if (a.trip_route) return a.driver_email ? `${a.trip_route} · ${a.driver_email}` : a.trip_route;
  return a.driver_email ?? null;
}

export default function AdminAlertsPage() {
  const qc = useQueryClient();
  const [openOnly, setOpenOnly] = useState(true);

  const params: AlertListParams = { status: openOnly ? "open" : undefined };
  const list = useCursorList<Alert, AlertListParams>({
    queryKey: QUERY_KEYS.adminAlerts(params),
    params,
    fetchPage: (args) => listAlerts(args),
  });

  // Any live frame refetches the authoritative feed; a critical one also toasts.
  const onEvent = useCallback(
    (data: unknown) => {
      const alert = parseAlertEvent(data);
      if (!alert) return;
      if (alert.severity === "critical") {
        toast.error(alert.message, { description: "New critical alert" });
      }
      qc.invalidateQueries({ queryKey: ["admin", "alerts"] });
    },
    [qc],
  );
  const { status: wsStatus } = useSocket("/ws/alerts/", { onEvent });
  const conn = CONN[wsStatus];

  const ack = useMutation({
    mutationFn: (id: number) => acknowledgeAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "alerts"] }),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Could not acknowledge the alert."),
  });

  return (
    <div className="grid gap-6">
      <section>
        <p className="label-mono text-xs text-muted-foreground">Operator console</p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Alerts</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Live operations incidents — SOS now, with deviation and overspeed to follow. Acknowledge
          an incident once it&apos;s handled.
        </p>
      </section>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-muted-foreground" />
            Incident log
          </CardTitle>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex h-5 items-center gap-1.5 rounded-full px-2 text-[0.6rem] font-medium",
                conn.cls,
              )}
            >
              <Radio className="size-3" />
              {conn.label}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-3 inline-flex rounded-lg border p-0.5 text-sm">
            <button
              type="button"
              onClick={() => setOpenOnly(true)}
              aria-pressed={openOnly}
              className={cn(
                "rounded-md px-3 py-1 transition-colors",
                openOnly ? "bg-primary text-primary-foreground" : "text-muted-foreground",
              )}
            >
              Open
            </button>
            <button
              type="button"
              onClick={() => setOpenOnly(false)}
              aria-pressed={!openOnly}
              className={cn(
                "rounded-md px-3 py-1 transition-colors",
                !openOnly ? "bg-primary text-primary-foreground" : "text-muted-foreground",
              )}
            >
              All
            </button>
          </div>

          {list.isLoading ? (
            <div className="grid gap-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          ) : list.isError ? (
            <p className="flex items-center gap-2 py-8 text-sm text-destructive">
              <AlertCircle className="size-4" />
              {list.error instanceof ApiError ? list.error.message : "Could not load alerts."}
            </p>
          ) : list.rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {openOnly ? "No open alerts. All clear." : "No alerts recorded yet."}
            </p>
          ) : (
            <ul className="grid gap-2">
              {list.rows.map((a) => {
                const target = describeTarget(a);
                return (
                  <li
                    key={a.id}
                    className={cn(
                      "flex items-start justify-between gap-3 rounded-lg border px-3 py-2.5",
                      a.severity === "critical" && a.status === "open"
                        ? "border-destructive/30 bg-destructive/5"
                        : "bg-muted/30",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <AlertSeverityBadge severity={a.severity} />
                        <span className="text-sm font-medium">
                          {TYPE_LABEL[a.type] ?? a.type}
                        </span>
                        {a.status === "acknowledged" && (
                          <span className="label-mono text-[0.6rem] text-muted-foreground">
                            acknowledged
                          </span>
                        )}
                      </div>
                      <p className="mt-1 truncate text-sm text-foreground">{a.message}</p>
                      <p className="label-mono mt-0.5 text-[0.6rem] text-muted-foreground">
                        {target ? `${target} · ` : ""}
                        {relativeTime(a.created_at)}
                      </p>
                    </div>
                    {a.status === "open" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => ack.mutate(a.id)}
                        disabled={ack.isPending}
                        className="shrink-0"
                      >
                        <Check className="size-4" />
                        Acknowledge
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          <CursorPager
            hasPrev={list.hasPrev}
            hasNext={list.hasNext}
            onPrev={list.prev}
            onNext={list.next}
            isFetching={list.isFetching}
          />
        </CardContent>
      </Card>
    </div>
  );
}
