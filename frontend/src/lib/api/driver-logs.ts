/**
 * Typed wrappers for the driver operational log endpoints (`/api/v1/driver/...`, IsDriver).
 *
 * `raiseSos` is the producer behind the admin alerts feed: it POSTs an SOS log, and the
 * backend records a CRITICAL incident + EMERGENCY notifications (best-effort fan-out). The
 * optional `trip` ties the SOS to a run; the service enforces it belongs to the driver.
 */

import { api } from "@/lib/axios";

import { unwrap } from "./error";
import { stripUndefined } from "./params";
import type { ApiEnvelope, DriverLog, DriverLogEventType } from "./types";

export interface SosPayload {
  notes?: string;
  trip?: number | null;
}

export interface DriverLogPayload extends SosPayload {
  event_type: DriverLogEventType;
}

/** POST /driver/sos/ -> 201, the committed SOS log (alerts fan-out is best-effort server-side). */
export async function raiseSos(payload: SosPayload = {}): Promise<DriverLog> {
  const { data } = await api.post<ApiEnvelope<DriverLog>>(
    "/driver/sos/",
    stripUndefined({ ...payload }),
  );
  return unwrap(data);
}

/** POST /driver/logs/ -> 201, a driver log of any event type (delay/breakdown/fuel/note/sos). */
export async function createDriverLog(payload: DriverLogPayload): Promise<DriverLog> {
  const { data } = await api.post<ApiEnvelope<DriverLog>>(
    "/driver/logs/",
    stripUndefined({ ...payload }),
  );
  return unwrap(data);
}
