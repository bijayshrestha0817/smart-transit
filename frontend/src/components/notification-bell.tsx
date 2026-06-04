"use client";

/**
 * Header notification bell (all roles). Shows an accurate unread count (from a dedicated
 * `?unread=true` query, not just the first page of the mixed feed), lists the recent feed,
 * and lets the user mark one / all read. Subscribes to `ws/notifications/` and refetches
 * the feed on any push frame (the REST feed is the source of truth). Owner-scoped server-side.
 *
 * The actionable rows are `DropdownMenuItem`s (with `onSelect` + `preventDefault` to keep the
 * menu open) so they join Radix's roving-tabindex model and stay keyboard/screen-reader reachable.
 */

import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellRing, CheckCheck } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useSocket } from "@/hooks/use-socket";
import { toApiError } from "@/lib/api/error";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api/notifications";
import type { AppNotification, NotificationType } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

const LABEL: Record<NotificationType, string> = {
  bus_arriving: "Bus arriving",
  route_delay: "Route delay",
  emergency: "Emergency",
  maintenance_due: "Maintenance due",
  trip_completed: "Trip completed",
};

/** Build a human line from the type + free-form payload. */
function describe(n: AppNotification): string {
  const p = n.payload_json ?? {};
  const route = typeof p.route_name === "string" ? p.route_name : null;
  switch (n.type) {
    case "trip_completed":
      return route ? `Trip completed on ${route}.` : "A trip you follow has completed.";
    case "bus_arriving":
      return route ? `Your bus is arriving on ${route}.` : "Your bus is arriving.";
    case "route_delay":
      return route ? `Delay reported on ${route}.` : "A delay was reported on your route.";
    case "maintenance_due":
      return typeof p.plate === "string"
        ? `Maintenance due for ${p.plate}.`
        : "A bus needs maintenance.";
    case "emergency":
      return typeof p.message === "string" ? p.message : "Emergency alert.";
    default:
      return LABEL[n.type] ?? "Notification";
  }
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function NotificationBell() {
  const queryClient = useQueryClient();

  // Recent feed (read + unread) for display…
  const feedQuery = useQuery({
    queryKey: QUERY_KEYS.notifications({}),
    queryFn: () => listNotifications({ page_size: 20 }),
  });
  // …and a dedicated unread query so the badge count is accurate (not capped by the feed page).
  const unreadQuery = useQuery({
    queryKey: QUERY_KEYS.notifications({ unread: true }),
    queryFn: () => listNotifications({ unread: true, page_size: 100 }),
  });

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }, [queryClient]);

  // Live: any push frame just triggers a refetch of the authoritative REST feed.
  const onEvent = useCallback(() => invalidate(), [invalidate]);
  useSocket("/ws/notifications/", { onEvent });

  const markRead = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: invalidate,
    onError: () => {},
  });
  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: invalidate,
    onError: (err) => toApiError(err),
  });

  const rows = feedQuery.data?.rows ?? [];
  const unread = unreadQuery.data?.rows.length ?? 0;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="Notifications" className="relative">
          {unread > 0 ? <BellRing className="size-4" /> : <Bell className="size-4" />}
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[0.6rem] font-medium leading-4 text-primary-foreground">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <DropdownMenuLabel className="flex items-center justify-between px-3 py-2">
          <span>Notifications</span>
          {unread > 0 && (
            <span className="text-xs font-normal text-muted-foreground">{unread} unread</span>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="my-0" />

        <div className="max-h-96 overflow-y-auto py-1">
          {feedQuery.isLoading ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">Loading…</p>
          ) : feedQuery.isError ? (
            <p className="px-3 py-6 text-center text-sm text-destructive">
              {toApiError(feedQuery.error).message}
            </p>
          ) : rows.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              You&apos;re all caught up.
            </p>
          ) : (
            rows.map((n) => {
              const isUnread = !n.read_at;
              return (
                <DropdownMenuItem
                  key={n.id}
                  onSelect={(e) => {
                    e.preventDefault();
                    if (isUnread) markRead.mutate(n.id);
                  }}
                  className={cn(
                    "flex items-start gap-2.5 px-3 py-2.5",
                    isUnread && "bg-primary/5",
                  )}
                >
                  <span
                    className={cn(
                      "mt-1.5 size-1.5 shrink-0 rounded-full",
                      isUnread ? "bg-primary" : "bg-transparent",
                    )}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
                      {LABEL[n.type] ?? "Notification"}
                    </span>
                    <span className="block text-sm leading-snug whitespace-normal">
                      {describe(n)}
                    </span>
                    <span className="label-mono text-[0.6rem] text-muted-foreground">
                      {relativeTime(n.created_at)}
                    </span>
                  </span>
                </DropdownMenuItem>
              );
            })
          )}
        </div>

        {unread > 0 && (
          <>
            <DropdownMenuSeparator className="my-0" />
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                markAll.mutate();
              }}
              disabled={markAll.isPending}
              className="justify-center gap-1.5 text-xs text-muted-foreground"
            >
              <CheckCheck className="size-3.5" />
              Mark all read
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
