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
import Link from "next/link";
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
import { useMe } from "@/hooks/use-auth";
import { useSocket } from "@/hooks/use-socket";
import { toApiError } from "@/lib/api/error";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api/notifications";
import { DASHBOARD_BY_ROLE } from "@/lib/auth-routes";
import { describe, LABEL, relativeTime } from "@/lib/notifications-format";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

export function NotificationBell() {
  const queryClient = useQueryClient();
  const { user } = useMe();

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

        {/* Guard on `user`: without it the href would be `/undefined/notifications`. */}
        {user && (
          <>
            <DropdownMenuSeparator className="my-0" />
            <DropdownMenuItem asChild className="justify-center text-xs">
              <Link href={`${DASHBOARD_BY_ROLE[user.role]}/notifications`}>See all</Link>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
