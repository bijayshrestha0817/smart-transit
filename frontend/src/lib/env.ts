/**
 * Centralized, validated access to public env vars.
 *
 * Only `NEXT_PUBLIC_*` vars are readable in the browser. The API base is the one
 * piece of wiring the whole client depends on, so we resolve it once here with a
 * dev default and re-export it as a typed constant.
 */

const DEFAULT_API_URL = "http://localhost:8000/api/v1";

export const env = {
  /** Base URL of the Django REST API, e.g. http://localhost:8000/api/v1 */
  apiUrl: process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || DEFAULT_API_URL,
} as const;
