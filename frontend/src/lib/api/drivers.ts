/**
 * Typed wrappers for the admin `/api/v1/admin/drivers/` endpoints (IsAdmin).
 *
 * CRUD over `User` rows with `role=driver` (the `role` field is never exposed or
 * settable; created drivers auto `is_verified=True`). `listDriverOptions` feeds the
 * buses assign-driver `Select`.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  Driver,
  PaginatedEnvelope,
  PaginationMeta,
} from "./types";

/** Query params accepted by the drivers list. */
export interface DriverListParams extends Record<string, unknown> {
  search?: string;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** Write body for create driver (password required). */
export interface DriverCreateInput {
  email: string;
  password: string;
  full_name?: string;
  phone?: string;
}

/** Write body for update driver (password optional). */
export interface DriverUpdateInput {
  email?: string;
  password?: string;
  full_name?: string;
  phone?: string;
}

/** GET /admin/drivers/ -> 200, cursor-paginated list. */
export async function adminListDrivers(
  params: DriverListParams = {},
): Promise<{ rows: Driver[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Driver>>("/admin/drivers/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /admin/drivers/{id}/ -> 200, single driver. */
export async function getDriver(id: number): Promise<Driver> {
  const { data } = await api.get<ApiEnvelope<Driver>>(`/admin/drivers/${id}/`);
  return unwrap(data);
}

/** POST /admin/drivers/ -> 201. Codes: duplicate_email, required. */
export async function createDriver(body: DriverCreateInput): Promise<Driver> {
  const { data } = await api.post<ApiEnvelope<Driver>>("/admin/drivers/", body);
  return unwrap(data);
}

/** PATCH /admin/drivers/{id}/ -> 200. */
export async function updateDriver(
  id: number,
  body: DriverUpdateInput,
): Promise<Driver> {
  const { data } = await api.patch<ApiEnvelope<Driver>>(
    `/admin/drivers/${id}/`,
    body,
  );
  return unwrap(data);
}

/** DELETE /admin/drivers/{id}/ -> 204 (soft delete + is_active=False). */
export async function deleteDriver(id: number): Promise<void> {
  await api.delete(`/admin/drivers/${id}/`);
}

/**
 * Fetch the first page of drivers for the assign-driver picker.
 *
 * The picker only needs a flat `Driver[]`; pagination metadata is dropped. A large
 * `page_size` keeps it to a single request for typical fleets.
 */
export async function listDriverOptions(): Promise<Driver[]> {
  const { rows } = await adminListDrivers({ page_size: 100 });
  return rows;
}
