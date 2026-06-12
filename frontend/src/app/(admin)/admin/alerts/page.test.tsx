/**
 * Integration test for the admin alerts feed.
 *
 * MSW serves the cursor feed (`/admin/alerts/`) and the acknowledge action
 * (`/admin/alerts/{id}/acknowledge/`) in the real `{data, meta, errors}` envelope. We
 * assert incidents render with a severity badge and that acknowledging fires the action.
 * The page opens a `/ws/alerts/` socket, so WebSocket is stubbed (the hook swallows the throw).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/test/msw/server";
import { API, http, ok, okPage } from "@/test/msw/handlers";

import AdminAlertsPage from "./page";

interface AlertRow {
  id: number;
  type: string;
  severity: string;
  message: string;
  trip: number | null;
  trip_route: string | null;
  driver: number | null;
  driver_email: string | null;
  status: string;
  payload_json: Record<string, unknown>;
  acknowledged_at: string | null;
  created_at: string;
}

const NOW = new Date().toISOString();

function alertRow(overrides: Partial<AlertRow> = {}): AlertRow {
  return {
    id: 1,
    type: "sos",
    severity: "critical",
    message: "SOS reported by driver #1",
    trip: null,
    trip_route: null,
    driver: 1,
    driver_email: "driver@example.com",
    status: "open",
    payload_json: {},
    acknowledged_at: null,
    created_at: NOW,
    ...overrides,
  };
}

const PAGINATION = { next: null, prev: null, page_size: 20 };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

beforeEach(() => {
  vi.stubGlobal(
    "WebSocket",
    class {
      onopen: (() => void) | null = null;
      onmessage: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      readyState = 0;
      close() {}
      send() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminAlertsPage", () => {
  it("lists incidents with a severity badge and acknowledges one", async () => {
    const ackedIds: number[] = [];
    server.use(
      http.get(`${API}/admin/alerts/`, () => okPage([alertRow()], PAGINATION)),
      http.post(`${API}/admin/alerts/:id/acknowledge/`, ({ params }) => {
        ackedIds.push(Number(params.id));
        return ok(alertRow({ status: "acknowledged", acknowledged_at: NOW }));
      }),
    );

    const user = userEvent.setup();
    render(<AdminAlertsPage />, { wrapper: makeWrapper() });

    expect(await screen.findByText("SOS reported by driver #1")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Acknowledge/i }));
    await waitFor(() => expect(ackedIds).toContain(1));
  });

  it("shows the all-clear empty state when there are no open alerts", async () => {
    server.use(http.get(`${API}/admin/alerts/`, () => okPage<AlertRow>([], PAGINATION)));

    render(<AdminAlertsPage />, { wrapper: makeWrapper() });

    expect(await screen.findByText("No open alerts. All clear.")).toBeInTheDocument();
  });
});
