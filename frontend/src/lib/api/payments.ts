/**
 * Typed wrapper for `POST /api/v1/payments/checkout/` (start a gateway payment for an
 * already-issued, pending ticket). External gateways currently return 400
 * `gateway_not_configured` (D4 stub); `wallet` is already settled at issue time.
 *
 * The gateway webhook (`/payments/webhook/{gateway}/`) is server-to-server (AllowAny)
 * and intentionally NOT called from the browser.
 */

import { api } from "@/lib/axios";

import { unwrap } from "./error";
import type { ApiEnvelope, CheckoutResult } from "./types";

/** POST /payments/checkout/ -> 200. Code: gateway_not_configured (external, D4). */
export async function checkout(ticketId: number): Promise<CheckoutResult> {
  const { data } = await api.post<ApiEnvelope<CheckoutResult>>("/payments/checkout/", {
    ticket: ticketId,
  });
  return unwrap(data);
}
