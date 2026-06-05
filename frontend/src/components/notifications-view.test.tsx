/**
 * Integration test for the full-page notifications view.
 *
 * MSW serves the cursor feed (`/notifications/`), the unread-filtered feed
 * (`?unread=true`), and the per-row read action (`/notifications/{id}/read/`),
 * matching the real `{data, meta, errors}` envelope. We assert the list renders,
 * the All/Unread filter narrows it, and clicking an unread row marks it read.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/test/msw/server";
import { API, http, ok, okPage } from "@/test/msw/handlers";

import { NotificationsView } from "./notifications-view";

interface Notif {
  id: number;
  type: string;
  payload_json: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

const NOW = new Date().toISOString();

function notif(overrides: Partial<Notif> = {}): Notif {
  return {
    id: 1,
    type: "bus_arriving",
    payload_json: { route_name: "Blue Line" },
    read_at: null,
    created_at: NOW,
    ...overrides,
  };
}

const FEED: Notif[] = [
  notif({ id: 1, type: "bus_arriving", payload_json: { route_name: "Blue Line" } }),
  notif({
    id: 2,
    type: "route_delay",
    payload_json: { route_name: "Red Line" },
    read_at: NOW,
  }),
];

const PAGINATION = { next: null, prev: null, page_size: 20 };

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

beforeEach(() => {
  // The view opens a notifications socket; stub WebSocket so jsdom never tries a
  // real connection (the hook catches the throw, so even a no-op class is fine).
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

describe("NotificationsView", () => {
  it("lists notifications, filters to unread, and marks one read", async () => {
    const readIds: number[] = [];

    server.use(
      http.get(`${API}/notifications/`, ({ request }) => {
        const url = new URL(request.url);
        const unread = url.searchParams.get("unread") === "true";
        const rows = unread ? FEED.filter((n) => !n.read_at) : FEED;
        return okPage(rows, PAGINATION);
      }),
      http.post(`${API}/notifications/:id/read/`, ({ params }) => {
        const id = Number(params.id);
        readIds.push(id);
        return ok(notif({ id, read_at: NOW }));
      }),
    );

    const user = userEvent.setup();
    render(<NotificationsView />, { wrapper: makeWrapper() });

    // Both notifications render initially (All filter).
    expect(
      await screen.findByText("Your bus is arriving on Blue Line."),
    ).toBeInTheDocument();
    expect(screen.getByText("Delay reported on Red Line.")).toBeInTheDocument();

    // Switch to the Unread filter -> the read "Red Line" delay drops out.
    await user.click(screen.getByRole("button", { name: "Unread" }));
    await waitFor(() =>
      expect(screen.queryByText("Delay reported on Red Line.")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Your bus is arriving on Blue Line.")).toBeInTheDocument();

    // Click the unread row -> fires the read mutation for its id.
    const row = screen.getByRole("button", { name: /Bus arriving — mark as read/i });
    await user.click(row);
    await waitFor(() => expect(readIds).toContain(1));
  });

  it("shows the empty state when the feed is empty", async () => {
    server.use(
      http.get(`${API}/notifications/`, () => okPage<Notif>([], PAGINATION)),
    );

    render(<NotificationsView />, { wrapper: makeWrapper() });

    expect(await screen.findByText("You're all caught up.")).toBeInTheDocument();
  });
});
