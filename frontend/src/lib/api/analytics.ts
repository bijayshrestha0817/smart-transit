/**
 * Typed wrapper for the admin analytics endpoints.
 *
 * Same envelope contract as the other `lib/api/*` modules: the KPI overview is a single
 * computed object (no pagination), so it returns `data` via `unwrap`. The Recharts /
 * time-series analytics endpoints land in a later P6 slice.
 */

import { api } from "@/lib/axios";

import { unwrap } from "./error";
import type { AdminKpis, ApiEnvelope } from "./types";

/** GET /admin/overview/kpis/ -> 200, single KPI object (no pagination; IsAdmin). */
export async function fetchAdminKpis(): Promise<AdminKpis> {
  const { data } = await api.get<ApiEnvelope<AdminKpis>>("/admin/overview/kpis/");
  return unwrap(data);
}
