/**
 * Typed wrappers for `/api/v1/notifications/` (in-app feed, any authenticated role).
 *
 * The feed is owner-scoped server-side (a foreign id 404s). `?unread=true` narrows to
 * unread. `read_at` null means unread. Live pushes arrive on `ws/notifications/` — the
 * UI just refetches the feed on any frame rather than parsing the push payload.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  AppNotification,
  PaginatedEnvelope,
  PaginationMeta,
} from "./types";

export interface NotificationListParams extends Record<string, unknown> {
  unread?: boolean;
  cursor?: string;
  page_size?: number;
}

/** GET /notifications/?unread= -> 200, cursor-paginated feed (newest first). */
export async function listNotifications(
  params: NotificationListParams = {},
): Promise<{ rows: AppNotification[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<AppNotification>>("/notifications/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** POST /notifications/{id}/read/ -> 200, the updated notification (idempotent; 404 foreign). */
export async function markNotificationRead(id: number): Promise<AppNotification> {
  const { data } = await api.post<ApiEnvelope<AppNotification>>(
    `/notifications/${id}/read/`,
  );
  return unwrap(data);
}

/** POST /notifications/read-all/ -> 200 `{ updated }`. */
export async function markAllNotificationsRead(): Promise<{ updated: number }> {
  const { data } = await api.post<ApiEnvelope<{ updated: number }>>(
    "/notifications/read-all/",
  );
  return unwrap(data);
}
