/**
 * Shared Axios instance for the Smart Transit API.
 *
 * Auth is cookie-based: the backend sets HttpOnly `st_access` / `st_refresh`
 * cookies that JS cannot read. We never touch tokens here — `withCredentials`
 * makes the browser attach and receive those cookies automatically. The only
 * client-side auth logic is the single-flight refresh below.
 */

import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { env } from "./env";

export const api = axios.create({
  baseURL: env.apiUrl,
  withCredentials: true, // send/receive the HttpOnly auth cookies
  headers: { "Content-Type": "application/json" },
});

/** Endpoints that must NOT trigger the refresh-and-retry dance. */
const AUTH_BYPASS = [
  "/auth/refresh/",
  "/auth/login/",
  "/auth/register/",
  "/auth/forgot-password/",
  "/auth/reset-password/",
  "/auth/verify-email/",
];

const isBypassed = (url: string | undefined): boolean =>
  !!url && AUTH_BYPASS.some((path) => url.includes(path));

/** Per-request flag so a retried request never loops back into refresh. */
type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

// --- Single-flight refresh coordination ---------------------------------
// While one refresh is in flight, concurrent 401s wait on the same promise
// instead of each firing their own refresh.
let refreshPromise: Promise<void> | null = null;

function runRefresh(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = api
      .post("/auth/refresh/")
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

/**
 * Called when refresh fails (or no session exists). Clears client auth state and
 * sends the user to /login. Registered by the app shell so this module stays free
 * of React/router imports.
 */
let onAuthFailure: (() => void) | null = null;

export function registerAuthFailureHandler(handler: () => void): void {
  onAuthFailure = handler;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;

    const shouldRefresh =
      status === 401 && original && !original._retried && !isBypassed(original.url);

    if (!shouldRefresh) {
      return Promise.reject(error);
    }

    original._retried = true;

    try {
      await runRefresh();
    } catch {
      // Refresh itself failed -> session is unrecoverable.
      onAuthFailure?.();
      return Promise.reject(error);
    }

    // Refresh succeeded: replay the original request with the rotated cookies.
    return api(original as AxiosRequestConfig);
  },
);
