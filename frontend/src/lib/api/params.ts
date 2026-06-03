/**
 * Drop keys whose value is `undefined` before sending query params.
 *
 * Axios would otherwise serialize `undefined` filters into the URL as empty
 * values, which several backend filters reject (and which pollutes the cursor a
 * page was minted under). Keeping `null`/`0`/`""` is intentional — only
 * `undefined` means "not set".
 */
export function stripUndefined<T extends Record<string, unknown>>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined),
  ) as Partial<T>;
}
