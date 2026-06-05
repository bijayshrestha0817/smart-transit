/**
 * Centralized, validated access to public env vars.
 *
 * Only `NEXT_PUBLIC_*` vars are readable in the browser. The API base is the one
 * piece of wiring the whole client depends on, so we resolve it once here with a
 * dev default and re-export it as a typed constant.
 */

const DEFAULT_API_URL = "http://localhost:8000/api/v1";

const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || DEFAULT_API_URL;

/**
 * Derive the WebSocket origin from the REST API URL: swap `http(s)→ws(s)` and drop
 * the path (the API lives at `/api/v1`, but the WS consumers mount at `/ws/...` off
 * the host root). Falls back to the dev default if the URL can't be parsed.
 */
function deriveWsUrl(httpApiUrl: string): string {
  try {
    const u = new URL(httpApiUrl);
    const proto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${u.host}`;
  } catch {
    return "ws://localhost:8000";
  }
}

export const env = {
  /** Base URL of the Django REST API, e.g. http://localhost:8000/api/v1 */
  apiUrl,
  /**
   * WebSocket origin (no trailing slash), e.g. ws://localhost:8000. Callers append
   * the consumer path: `${env.wsUrl}/ws/driver/{tripId}/`. Set `NEXT_PUBLIC_WS_URL`
   * explicitly per environment (Docker exposes Daphne on :9000; prod must be `wss://`).
   */
  wsUrl: process.env.NEXT_PUBLIC_WS_URL?.replace(/\/+$/, "") || deriveWsUrl(apiUrl),
} as const;
