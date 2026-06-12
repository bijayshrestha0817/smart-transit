/**
 * Test for the driver SOS control — the producer behind the admin alerts feed.
 *
 * MSW serves `POST /driver/sos/` in the `{data, meta, errors}` envelope. We assert the
 * confirm dialog opens, "Send SOS" fires the request with the trip id, and the dialog closes.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { API, http, ok } from "@/test/msw/handlers";

import { DriverSosButton } from "./driver-sos-button";

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe("DriverSosButton", () => {
  it("confirms then POSTs an SOS with the trip id", async () => {
    let body: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/driver/sos/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return ok({
          id: 1,
          event_type: "sos",
          notes: "",
          trip: 5,
          timestamp: new Date().toISOString(),
          created_at: new Date().toISOString(),
        });
      }),
    );

    const user = userEvent.setup();
    render(<DriverSosButton tripId={5} />, { wrapper: makeWrapper() });

    // Trigger opens the confirm dialog (guards against accidental taps).
    await user.click(screen.getByRole("button", { name: "SOS" }));
    expect(await screen.findByText("Raise an emergency SOS?")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send SOS" }));
    await waitFor(() => expect(body).toEqual({ trip: 5 }));
  });
});
