/**
 * Typed wrappers for the public `/api/v1/stops/` endpoints (AllowAny).
 *
 * READ-ONLY: stop writes go through `routes.assignStops` (the destructive
 * full-replace on a route). The list is cursor-paginated; `?near=<lat>,<lng>`
 * (comma, no space) + optional `?radius=<km>` does proximity search.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  BusStop,
  PaginatedEnvelope,
  PaginationMeta,
} from "./types";

/** Query params accepted by the stops list. */
export interface StopListParams extends Record<string, unknown> {
  route?: number;
  /** "<lat>,<lng>" with no space; malformed -> 400 invalid_near (field "near"). */
  near?: string;
  /** Proximity radius in km; defaults to 1.0 server-side. */
  radius?: number;
  search?: string;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** GET /stops/ -> 200, cursor-paginated list. */
export async function listStops(
  params: StopListParams = {},
): Promise<{ rows: BusStop[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<BusStop>>("/stops/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /stops/{id}/ -> 200, single stop. */
export async function getStop(id: number): Promise<BusStop> {
  const { data } = await api.get<ApiEnvelope<BusStop>>(`/stops/${id}/`);
  return unwrap(data);
}
