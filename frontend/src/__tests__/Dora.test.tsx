import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Dora from "../pages/Dora";
import { FilterProvider } from "../state/FilterContext";
import type { DoraMetricsResponse } from "../api/client";

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
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => body } as Response)
  );
}

afterEach(() => vi.unstubAllGlobals());

const SERVICE_WITH_NO_RUNS = {
  service: "quiet-service",
  deployment_frequency_per_week: 0,
  lead_time_hours: null,
  change_failure_rate_pct: 0,
  mttr_hours: null,
  total_deployments: 0,
  total_failures: 0,
};

describe("DORA page", () => {
  it("always states that the metrics are CI-derived, not production measurements", async () => {
    mockDora({ window_days: 30, services: [] });
    renderPage();

    expect(
      await screen.findByText(/derived from CI runs/i)
    ).toBeInTheDocument();
  });

  it("renders an empty state when no repository is tracked", async () => {
    mockDora({ window_days: 30, services: [] });
    renderPage();

    expect(await screen.findByText("Nothing to measure yet")).toBeInTheDocument();
  });

  it("does not report 0% failure rate for a window containing no completed runs", async () => {
    // The backend still returns 0.0 here (a known defect fixed in Stage 6), so
    // the UI must not repeat it as though it were a healthy measurement.
    mockDora({ window_days: 30, services: [SERVICE_WITH_NO_RUNS] });
    renderPage();

    await waitFor(() => expect(screen.getByText("quiet-service")).toBeInTheDocument());
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
    expect(screen.queryByText("0/wk")).not.toBeInTheDocument();
  });

  it("shows real measurements when the window contains runs", async () => {
    mockDora({
      window_days: 90,
      services: [{
        service: "payments",
        deployment_frequency_per_week: 2.64,
        lead_time_hours: 0,
        change_failure_rate_pct: 22.7,
        mttr_hours: 0.1,
        total_deployments: 34,
        total_failures: 10,
      }],
    });
    renderPage();

    expect(await screen.findByText("2.64/wk")).toBeInTheDocument();
    expect(screen.getByText("22.7%")).toBeInTheDocument();
    expect(screen.getByText("Elevated")).toBeInTheDocument();
  });

  it("surfaces an API failure instead of rendering an empty table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response));
    renderPage();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
