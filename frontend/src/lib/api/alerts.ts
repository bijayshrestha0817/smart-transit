/**
 * Typed wrappers for the admin alerts feed (`/api/v1/admin/alerts/`, IsAdmin).
 *
 * The list is the cursor-paginated incident log the UI seeds from before `/ws/alerts/`
 * takes over with live frames. `?status=open` / `?severity=` narrow it. Acknowledge marks
 * one incident handled (idempotent; a foreign/unknown id 404s).
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  Alert,
  AlertSeverity,
  AlertStatus,
  ApiEnvelope,
  PaginatedEnvelope,
  PaginationMeta,
} from "./types";

export interface AlertListParams extends Record<string, unknown> {
  status?: AlertStatus;
  severity?: AlertSeverity;
  cursor?: string;
  page_size?: number;
}

/** GET /admin/alerts/?status=&severity= -> 200, cursor-paginated (newest first; IsAdmin). */
export async function listAlerts(
  params: AlertListParams = {},
): Promise<{ rows: Alert[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Alert>>("/admin/alerts/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** POST /admin/alerts/{id}/acknowledge/ -> 200, the updated alert (idempotent; 404 unknown). */
export async function acknowledgeAlert(id: number): Promise<Alert> {
  const { data } = await api.post<ApiEnvelope<Alert>>(`/admin/alerts/${id}/acknowledge/`);
  return unwrap(data);
}
