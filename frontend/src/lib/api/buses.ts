/**
 * Typed wrappers for the admin `/api/v1/admin/buses/` endpoints (IsAdmin).
 *
 * CRUD plus two custom actions: assign-driver (the serializer validates first, so
 * an invalid driver is a 400 `invalid_driver`, NOT a 404 — branch on the code) and
 * mark-maintenance (sets `status="maintenance"`; the note is not persisted).
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  Bus,
  BusStatus,
  PaginatedEnvelope,
  PaginationMeta,
} from "./types";

/** Query params accepted by the buses list. */
export interface BusListParams extends Record<string, unknown> {
  status?: BusStatus;
  assigned_driver?: number;
  search?: string;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** Write body for create/update bus. */
export interface BusInput {
  plate: string;
  capacity: number;
  status?: BusStatus;
  assigned_driver?: number | null;
}

/** GET /admin/buses/ -> 200, cursor-paginated list. */
export async function adminListBuses(
  params: BusListParams = {},
): Promise<{ rows: Bus[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Bus>>("/admin/buses/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /admin/buses/{id}/ -> 200, single bus. */
export async function getBus(id: number): Promise<Bus> {
  const { data } = await api.get<ApiEnvelope<Bus>>(`/admin/buses/${id}/`);
  return unwrap(data);
}

/** POST /admin/buses/ -> 201. Codes: duplicate_plate, required. */
export async function createBus(body: BusInput): Promise<Bus> {
  const { data } = await api.post<ApiEnvelope<Bus>>("/admin/buses/", body);
  return unwrap(data);
}

/** PATCH /admin/buses/{id}/ -> 200. */
export async function updateBus(id: number, body: Partial<BusInput>): Promise<Bus> {
  const { data } = await api.patch<ApiEnvelope<Bus>>(`/admin/buses/${id}/`, body);
  return unwrap(data);
}

/** DELETE /admin/buses/{id}/ -> 204 (soft delete). */
export async function deleteBus(id: number): Promise<void> {
  await api.delete(`/admin/buses/${id}/`);
}

/**
 * PATCH /admin/buses/{id}/assign-driver/ -> 200, returns the updated bus.
 *
 * Body `{ driver_id }`. An invalid/non-driver target is a 400 `invalid_driver`
 * (the 404 path only fires on a soft-delete race) — branch on the code.
 */
export async function assignDriver(id: number, driverId: number): Promise<Bus> {
  const { data } = await api.patch<ApiEnvelope<Bus>>(
    `/admin/buses/${id}/assign-driver/`,
    { driver_id: driverId },
  );
  return unwrap(data);
}

/** PATCH /admin/buses/{id}/maintenance/ -> 200. Sets status="maintenance"; note not persisted. */
export async function markMaintenance(id: number, note?: string): Promise<Bus> {
  const { data } = await api.patch<ApiEnvelope<Bus>>(
    `/admin/buses/${id}/maintenance/`,
    { note },
  );
  return unwrap(data);
}
