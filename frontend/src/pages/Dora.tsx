import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge from "../components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { fetchDoraMetrics } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";
import { formatHours, formatPercent, UNAVAILABLE } from "../format";

const ELEVATED_FAILURE_RATE_PCT = 20;

export default function Dora() {
  const { windowDays } = useFilters();
  const { state, reload } = useAsync(() => fetchDoraMetrics(windowDays), [windowDays]);

  return (
    <>
      <PageHeader
        title="DORA"
        description="Per-repository delivery indicators, worst performing first."
      />

      <Banner tone="warning" title="Four of five DORA metrics, derived from CI runs">
        Current DORA defines five metrics. DevPulse computes four of the legacy
        set, and derives them from workflow runs standing in for deployments
        because no deployment provider is connected. Deployment Rework Rate
        requires deployment data and is reported as unavailable rather than
        estimated.
      </Banner>

      {state.status === "loading" && <LoadingState label="Loading DORA metrics" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && state.data.services.length === 0 && (
        <EmptyState
          title="Nothing to measure yet"
          body="No repositories are tracked, so there is no delivery activity to compute metrics from."
        />
      )}

      {state.status === "success" && state.data.services.length > 0 && (
        <>
          <section className="section">
            <h2 className="section__title">By repository</h2>
            <div className="card scroll-x">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Deploy frequency</th>
                    <th>Lead time</th>
                    <th>Change failure rate</th>
                    <th>Recovery time</th>
                    <th>Rework rate</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.services.map((service) => {
                    // A service with no completed runs in the window has no rate
                    // to report; 0 would read as healthy (rules.md 11).
                    const hasCompletedRuns =
                      service.total_deployments + service.total_failures > 0;
                    return (
                    <tr key={service.service}>
                      <td style={{ fontWeight: 600 }}>{service.service}</td>
                      <td className={`data-table__numeric${hasCompletedRuns ? "" : " data-table__unavailable"}`}>
                        {hasCompletedRuns ? `${service.deployment_frequency_per_week}/wk` : UNAVAILABLE}
                      </td>
                      <td className={`data-table__numeric${service.lead_time_hours === null ? " data-table__unavailable" : ""}`}>
                        {formatHours(service.lead_time_hours)}
                      </td>
                      <td className={`data-table__numeric${hasCompletedRuns ? "" : " data-table__unavailable"}`}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                          {hasCompletedRuns
                            ? formatPercent(service.change_failure_rate_pct)
                            : UNAVAILABLE}
                          {hasCompletedRuns &&
                            service.change_failure_rate_pct >= ELEVATED_FAILURE_RATE_PCT && (
                            <StatusBadge tone="danger">Elevated</StatusBadge>
                          )}
                        </span>
                      </td>
                      <td className={`data-table__numeric${service.mttr_hours === null ? " data-table__unavailable" : ""}`}>
                        {formatHours(service.mttr_hours)}
                      </td>
                      <td className="data-table__unavailable" title="Requires deployment data">
                        {UNAVAILABLE}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {(() => {
            const plotted = state.data.services.filter(
              (service) => service.total_deployments + service.total_failures > 0
            );
            if (plotted.length === 0) return null;
            return (
          <section className="section">
            <h2 className="section__title">Change failure rate</h2>
            <p className="section__hint">
              Share of completed workflow runs that failed. Bars at or above{" "}
              {ELEVATED_FAILURE_RATE_PCT}% are highlighted.
            </p>
            <div className="card" style={{ height: 320 }}>
              <ResponsiveContainer>
                <BarChart data={plotted} margin={{ top: 8, right: 8, left: -12, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="service" tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
                         axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                  <YAxis unit="%" tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
                         axisLine={false} tickLine={false} />
                  <Tooltip
                    cursor={{ fill: "var(--surface-elevated)" }}
                    contentStyle={{
                      background: "var(--surface-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "var(--text-primary)" }}
                    formatter={(value: number) => [`${value}%`, "Change failure rate"]}
                  />
                  <Bar dataKey="change_failure_rate_pct" radius={[4, 4, 0, 0]} maxBarSize={64}>
                    {plotted.map((service) => (
                      <Cell
                        key={service.service}
                        fill={service.change_failure_rate_pct >= ELEVATED_FAILURE_RATE_PCT
                          ? "var(--danger)" : "var(--accent)"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
            );
          })()}
        </>
      )}
    </>
  );
}
