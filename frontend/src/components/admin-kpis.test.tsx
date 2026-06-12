import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { AdminKpis } from "@/lib/api/types";
import { API, fail, http, ok } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";

import { AdminKpis as AdminKpisCard } from "./admin-kpis";

const KPIS_URL = `${API}/admin/overview/kpis/`;

const KPIS: AdminKpis = {
  active_buses: 4,
  total_buses: 20,
  buses_active: 9,
  buses_idle: 7,
  buses_in_maintenance: 3,
  buses_retired: 1,
  scheduled_trips: 50,
  active_trips: 4,
  completed_trips: 240,
  cancelled_trips: 6,
  scheduled_trips_today: 5,
  active_trips_today: 4,
  completed_trips_today: 11,
  cancelled_trips_today: 2,
  passengers_today: 128,
  revenue: "1530.00",
  avg_delay: 12.5,
  open_alerts: 1,
  maintenance_due: 3,
  total_routes: 14,
  total_drivers: 22,
  verified_drivers: 19,
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("AdminKpis", () => {
  it("renders the headline KPIs from the envelope", async () => {
    server.use(http.get(KPIS_URL, () => ok(KPIS)));

    render(<AdminKpisCard />, { wrapper: makeWrapper() });

    // Money is rendered as a localized string, avg_delay with its unit.
    expect(await screen.findByText("Rs 1530.00")).toBeInTheDocument();
    expect(screen.getByText("12.5 min")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("Active buses")).toBeInTheDocument();
    expect(screen.getByText("19 verified")).toBeInTheDocument();
  });

  it("shows an em dash when avg_delay is null (no completed trips)", async () => {
    server.use(http.get(KPIS_URL, () => ok({ ...KPIS, avg_delay: null })));

    render(<AdminKpisCard />, { wrapper: makeWrapper() });

    expect(await screen.findByText("—")).toBeInTheDocument();
    expect(screen.getByText("no completed trips yet")).toBeInTheDocument();
  });

  it("surfaces the API error message", async () => {
    server.use(http.get(KPIS_URL, () => fail(500, "server_error", null, "Could not load KPIs")));

    render(<AdminKpisCard />, { wrapper: makeWrapper() });

    await waitFor(() => expect(screen.getByText("Could not load KPIs")).toBeInTheDocument());
  });
});
