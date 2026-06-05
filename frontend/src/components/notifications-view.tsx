"use client";

/**
 * Full-page in-app notifications feed, shared by every role's `/…/notifications`
 * route. Mirrors the bell's data flow (cursor feed + a broad `["notifications"]`
 * invalidation that keeps the header badge in sync) but with room for full rows,
 * an All/Unread filter, and prev/next paging.
 *
 * The unread toggle flows through `params` (NOT a separate cursor state) so the
 * `useCursorList` hook resets to page 1 on every filter change — a cursor minted
 * for the mixed feed 404s ("Invalid cursor") if replayed against the unread feed.
 */

import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, BellOff, CheckCheck } from "lucide-react";

import { CursorPager } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCursorList } from "@/hooks/use-cursor-list";
import { useSocket } from "@/hooks/use-socket";
import { toApiError } from "@/lib/api/error";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationListParams,
} from "@/lib/api/notifications";
import type { AppNotification } from "@/lib/api/types";
import { describe, ICON, LABEL, relativeTime } from "@/lib/notifications-format";
import { QUERY_KEYS } from "@/lib/queryClient";
import { cn } from "@/lib/utils";

export function NotificationsView() {
  const queryClient = useQueryClient();
  const [showUnread, setShowUnread] = useState(false);

  // The filter lives in `params` so the cursor hook resets on every change.
  const params: NotificationListParams = { unread: showUnread ? true : undefined };
  const list = useCursorList<AppNotification, NotificationListParams>({
    queryKey: QUERY_KEYS.notifications(params),
    params,
    fetchPage: (args) => listNotifications(args),
  });

  // Broad invalidation: refreshes this page AND the header bell badge in one go.
  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }, [queryClient]);

  // Live: any push frame just triggers a refetch of the authoritative REST feed.
  useSocket("/ws/notifications/", { onEvent: invalidate });

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

  const rows = list.rows;
  const unreadCount = rows.filter((n) => !n.read_at).length;

  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label-mono text-xs text-muted-foreground">Inbox</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">
            Notifications
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Arrivals, delays, and alerts for the routes and rides you follow.
            {unreadCount > 0 ? ` ${unreadCount} unread on this page.` : ""}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || unreadCount === 0}
        >
          <CheckCheck className="size-4" />
          Mark all read
        </Button>
      </header>

      <div className="flex" role="group" aria-label="Filter notifications">
        <div className="inline-flex rounded-lg border p-0.5">
          <Button
            type="button"
            size="sm"
            variant={showUnread ? "ghost" : "secondary"}
            aria-pressed={!showUnread}
            onClick={() => setShowUnread(false)}
          >
            All
          </Button>
          <Button
            type="button"
            size="sm"
            variant={showUnread ? "secondary" : "ghost"}
            aria-pressed={showUnread}
            onClick={() => setShowUnread(true)}
          >
            Unread
          </Button>
        </div>
      </div>

      {list.isError ? (
        <ErrorState message={toApiError(list.error).message} />
      ) : list.isLoading ? (
        <div className="grid gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="grid gap-2">
          {rows.map((n) => (
            <NotificationRow
              key={n.id}
              notification={n}
              onMarkRead={() => markRead.mutate(n.id)}
            />
          ))}
        </ul>
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

function NotificationRow({
  notification: n,
  onMarkRead,
}: {
  notification: AppNotification;
  onMarkRead: () => void;
}) {
  const isUnread = !n.read_at;
  const Icon = ICON[n.type];

  // Clicking an unread row marks it read; read rows are inert. Rendered as a
  // <button> so it's keyboard- and screen-reader-reachable when actionable.
  return (
    <li>
      <button
        type="button"
        disabled={!isUnread}
        onClick={isUnread ? onMarkRead : undefined}
        aria-label={isUnread ? `${LABEL[n.type]} — mark as read` : LABEL[n.type]}
        className={cn(
          "flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors",
          isUnread
            ? "bg-primary/5 hover:bg-primary/10 cursor-pointer"
            : "bg-card cursor-default",
        )}
      >
        <span
          className={cn(
            "mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg",
            isUnread ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
          )}
          aria-hidden
        >
          <Icon className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
            {LABEL[n.type] ?? "Notification"}
          </span>
          <span className="block text-sm leading-snug">{describe(n)}</span>
          <span className="label-mono text-[0.6rem] text-muted-foreground">
            {relativeTime(n.created_at)}
          </span>
        </span>
        {isUnread && (
          <span
            className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
            aria-hidden
          />
        )}
      </button>
    </li>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed py-16 text-center text-sm text-muted-foreground">
      <BellOff className="size-5" />
      <p>You&apos;re all caught up.</p>
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
