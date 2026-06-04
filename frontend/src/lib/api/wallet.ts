/**
 * Typed wrappers for `/api/v1/wallet/` (passenger store credit).
 *
 * The wallet is funded by ticket refunds (no external top-up this slice). `balance` and
 * ledger `amount`/`balance_after` are decimal STRINGS — keep them as strings for display
 * and only `parseFloat` for arithmetic.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  PaginationMeta,
  WalletTransaction,
} from "./types";

export interface WalletTxnListParams extends Record<string, unknown> {
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** GET /wallet/ -> 200 `{ balance }`. */
export async function getWalletBalance(): Promise<{ balance: string }> {
  const { data } = await api.get<ApiEnvelope<{ balance: string }>>("/wallet/");
  return unwrap(data);
}

/** GET /wallet/transactions/ -> 200, cursor-paginated ledger (newest first). */
export async function listWalletTransactions(
  params: WalletTxnListParams = {},
): Promise<{ rows: WalletTransaction[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<WalletTransaction>>(
    "/wallet/transactions/",
    { params: stripUndefined(params) },
  );
  return unwrapPage(data);
}
