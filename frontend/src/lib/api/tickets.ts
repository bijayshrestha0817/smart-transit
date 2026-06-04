/**
 * Typed wrappers for `/api/v1/tickets/` (passenger ticketing).
 *
 * Issue takes `{ trip, gateway }` — the fare is server-authoritative (never sent).
 * `gateway: "wallet"` settles synchronously (→ 201 with status `active`, or 400
 * `insufficient_balance`); external gateways return a `pending` ticket and currently
 * 400 `gateway_not_configured` at checkout (D4 stub). Same `{data,meta,errors}` envelope.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  PaginationMeta,
  PaymentGateway,
  Ticket,
  TicketStatus,
} from "./types";

export interface TicketListParams extends Record<string, unknown> {
  status?: TicketStatus;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

export interface IssueTicketInput {
  trip: number;
  gateway: PaymentGateway;
}

/** GET /tickets/ -> 200, cursor-paginated list of the caller's own tickets. */
export async function listTickets(
  params: TicketListParams = {},
): Promise<{ rows: Ticket[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Ticket>>("/tickets/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /tickets/{id}/ -> 200 (owner/admin; 404 if foreign). */
export async function getTicket(id: number): Promise<Ticket> {
  const { data } = await api.get<ApiEnvelope<Ticket>>(`/tickets/${id}/`);
  return unwrap(data);
}

/** POST /tickets/ -> 201. Codes: invalid_trip, insufficient_balance, gateway_not_configured. */
export async function issueTicket(body: IssueTicketInput): Promise<Ticket> {
  const { data } = await api.post<ApiEnvelope<Ticket>>("/tickets/", body);
  return unwrap(data);
}

/** POST /tickets/{id}/refund/ -> 200 (store credit). Codes: 409 ticket_not_refundable, 404 foreign. */
export async function refundTicket(id: number): Promise<Ticket> {
  const { data } = await api.post<ApiEnvelope<Ticket>>(`/tickets/${id}/refund/`);
  return unwrap(data);
}
