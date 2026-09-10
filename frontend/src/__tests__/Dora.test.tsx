import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Dora from "../pages/Dora";
import { FilterProvider } from "../state/FilterContext";
import type { DoraMetricsResponse, ServiceDoraMetrics } from "../api/client";

function renderPage() {
  return render(
    <MemoryRouter>
      <FilterProvider>
        <Dora />
      </FilterProvider>
    </MemoryRouter>
  );
}

function mockDora(body: DoraMetricsResponse) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => body } as Response));
}

afterEach(() => vi.unstubAllGlobals());

const UNMEASURABLE: ServiceDoraMetrics = {
  service: "no-deploy-source",
  deployment_source: "NONE",
  unavailable_reason:
    "No deployment provider is connected and no deployment workflow has been configured.",
  deployment_frequency_per_week: null,
  lead_time_hours: null,
  change_failure_rate_pct: null,
  failed_deployment_recovery_hours: null,
  deployment_rework_rate_pct: null,
  total_deployments: 0,
  total_failures: 0,
};

const MEASURED: ServiceDoraMetrics = {
  service: "payments",
  deployment_source: "CONFIGURED_WORKFLOW",
  unavailable_reason: null,
  deployment_frequency_per_week: 2.5,
  lead_time_hours: 1.25,
  change_failure_rate_pct: 22.7,
  failed_deployment_recovery_hours: 0.5,
  deployment_rework_rate_pct: 12.5,
  total_deployments: 10,
  total_failures: 3,
};

describe("DORA page", () => {
  it("states that metrics come from deployments, not CI runs", async () => {
    mockDora({ window_days: 30, services: [MEASURED] });
    renderPage();

    expect(await screen.findByText(/never from CI runs/i)).toBeInTheDocument();
  });

  it("renders an empty state when no repository is tracked", async () => {
    mockDora({ window_days: 30, services: [] });
    renderPage();

    expect(await screen.findByText("Nothing to measure yet")).toBeInTheDocument();
  });

  it("never renders a zero for a service with no deployment source", async () => {
    mockDora({ window_days: 30, services: [UNMEASURABLE] });
    renderPage();

    await waitFor(() =>
      expect(screen.getAllByText("no-deploy-source").length).toBeGreaterThan(0)
    );
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
    expect(screen.queryByText("0/wk")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });

  it("explains why an unmeasurable service has no numbers", async () => {
    mockDora({ window_days: 30, services: [UNMEASURABLE] });
    renderPage();

    expect(
      await screen.findByText(/Deployment-derived metrics are unavailable/i)
    ).toBeInTheDocument();
  });

  it("shows all five metrics when a deployment source exists", async () => {
    mockDora({ window_days: 30, services: [MEASURED] });
    renderPage();

    await waitFor(() => expect(screen.getAllByText("payments").length).toBeGreaterThan(0));
    expect(screen.getAllByText("2.5").length).toBeGreaterThan(0);   // frequency
    expect(screen.getAllByText("22.7%").length).toBeGreaterThan(0); // fail rate
    expect(screen.getAllByText("12.5%").length).toBeGreaterThan(0); // rework rate
    expect(screen.getAllByText("Elevated").length).toBeGreaterThan(0);
  });

  it("surfaces an API failure instead of rendering an empty table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response));
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
