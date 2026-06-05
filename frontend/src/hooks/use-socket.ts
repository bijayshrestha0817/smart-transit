"use client";

/**
 * Resilient WebSocket hook for the real-time tracking streams.
 *
 * Auth is cookie-only: the HttpOnly `st_access` cookie rides the handshake
 * automatically (same-site), so we NEVER put a token in the URL or in JS. The close
 * code drives recovery:
 *   - 401 (unauthenticated): the access cookie expired. Hit a cheap REST endpoint
 *     (`GET /auth/me/`) once so the axios 401→refresh interceptor rotates the cookie,
 *     then reconnect once. A second 401 means refresh failed → stop (axios already
 *     redirected to /login).
 *   - 403 (forbidden): wrong role / not this trip's driver. Stop, no retry.
 *   - anything else (incl. 1006): transient → exponential backoff + jitter, capped.
 * Reconnects when the tab becomes visible again. The token is only checked at handshake,
 * so a long-open socket is never dropped mid-stream.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { getMe } from "@/lib/api/auth";
import { env } from "@/lib/env";

export type SocketStatus = "idle" | "connecting" | "open" | "closed" | "forbidden";

interface UseSocketOptions {
  /** Called with each parsed JSON frame from the server. */
  onEvent?: (data: unknown) => void;
  /** When false, the socket stays closed (e.g. trip not in progress yet). */
  enabled?: boolean;
}

const BASE_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
// Close codes emitted by the backend consumers (realtime/consumers.py): the canonical
// values are 4401 (unauthenticated) and 4403 (forbidden) — RFC-6455 app close codes live
// in 4000–4999. We also accept the bare 401/403 forms in case an intermediary strips the
// leading 4, so recovery is never missed regardless of which form arrives.
const WS_UNAUTHENTICATED_CODES: number[] = [4401, 401];
const WS_FORBIDDEN_CODES: number[] = [4403, 403];

export interface UseSocketResult {
  status: SocketStatus;
  lastError: string | null;
  /** Send a frame (object is JSON-stringified). Returns false if the socket isn't open. */
  send: (data: unknown) => boolean;
}

export function useSocket(
  path: string,
  { onEvent, enabled = true }: UseSocketOptions = {},
): UseSocketResult {
  const [status, setStatus] = useState<SocketStatus>("idle");
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  // Keep the latest handler in a ref so a new closure never forces a reconnect.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });

  const send = useCallback((data: unknown): boolean => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === "string" ? data : JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    // When disabled we simply don't connect; the returned status is derived as "idle"
    // (see the return below) so we never call setState synchronously in the effect body.
    if (!enabled) return;

    const url = `${env.wsUrl}${path}`;
    let attempt = 0;
    let didRefresh = false; // one auto-refresh per session gap
    let stopped = false; // forbidden / unmounted -> never reconnect
    let timer: ReturnType<typeof setTimeout> | null = null;

    const clearTimer = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const scheduleReconnect = () => {
      if (stopped) return;
      const backoff = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
      attempt += 1;
      const jitter = Math.random() * backoff * 0.5;
      clearTimer();
      timer = setTimeout(connect, backoff + jitter);
    };

    const handleUnauthenticated = async () => {
      if (didRefresh) {
        stopped = true;
        setStatus("forbidden");
        setLastError("Your session expired. Please sign in again.");
        return;
      }
      didRefresh = true;
      setStatus("connecting");
      try {
        // Triggers the axios 401→refresh→retry dance, rotating the cookie.
        await getMe();
        if (!stopped) connect();
      } catch {
        // Refresh failed; the axios interceptor has already redirected to /login.
        stopped = true;
        setStatus("forbidden");
        setLastError("Your session expired. Please sign in again.");
      }
    };

    function connect() {
      if (stopped) return;
      clearTimer();
      setStatus("connecting");

      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        didRefresh = false;
        setStatus("open");
        setLastError(null);
      };

      ws.onmessage = (e: MessageEvent) => {
        try {
          onEventRef.current?.(JSON.parse(e.data as string));
        } catch {
          // Ignore non-JSON frames.
        }
      };

      ws.onerror = () => {
        // A close event always follows; recovery is handled there.
      };

      ws.onclose = (e: CloseEvent) => {
        if (wsRef.current === ws) wsRef.current = null;
        if (stopped) return;

        if (WS_FORBIDDEN_CODES.includes(e.code)) {
          stopped = true;
          setStatus("forbidden");
          setLastError("You are not permitted to view this stream.");
          return;
        }
        if (WS_UNAUTHENTICATED_CODES.includes(e.code)) {
          void handleUnauthenticated();
          return;
        }
        setStatus("closed");
        scheduleReconnect();
      };
    }

    const onVisibility = () => {
      if (stopped || document.visibilityState !== "visible") return;
      const ws = wsRef.current;
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        attempt = 0;
        connect();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    connect();

    return () => {
      stopped = true;
      clearTimer();
      document.removeEventListener("visibilitychange", onVisibility);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
        try {
          ws.close();
        } catch {
          // already closing
        }
      }
    };
  }, [path, enabled]);

  // Derive "idle" while disabled rather than writing state in the effect.
  return { status: enabled ? status : "idle", lastError, send };
}
