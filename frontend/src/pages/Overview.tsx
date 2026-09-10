import PageHeader from "../components/ui/PageHeader";
import MetricCard from "../components/ui/MetricCard";
import Banner from "../components/ui/Banner";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { fetchDoraMetrics, type ServiceDoraMetrics } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";
import { formatHours, formatPercent } from "../format";
import { Link } from "react-router-dom";

/** Aggregates per-service rows into one delivery picture. */
function aggregate(services: ServiceDoraMetrics[]) {
  const deployments = services.reduce((sum, s) => sum + s.total_deployments, 0);
  const failures = services.reduce((sum, s) => sum + s.total_failures, 0);
  const frequency = services.reduce((sum, s) => sum + s.deployment_frequency_per_week, 0);

  const leadTimes = services.map((s) => s.lead_time_hours).filter((v): v is number => v !== null);
  const recoveries = services.map((s) => s.mttr_hours).filter((v): v is number => v !== null);
  const mean = (values: number[]) =>
    values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

  // With no completed runs in the window there is nothing to rate. Reporting a
  // rate of 0 would present absent data as a healthy result (rules.md 11).
  const hasCompletedRuns = deployments + failures > 0;

  return {
    deployments,
    failures,
    hasCompletedRuns,
    frequency: hasCompletedRuns ? Number(frequency.toFixed(2)) : null,
    failureRate: hasCompletedRuns ? (failures / (deployments + failures)) * 100 : null,
    leadTime: mean(leadTimes),
    recovery: mean(recoveries),
  };
}

export default function Overview() {
  const { windowDays } = useFilters();
  const { state, reload } = useAsync(() => fetchDoraMetrics(windowDays), [windowDays]);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Delivery signal across every tracked repository, for the selected window."
      />

      <Banner tone="warning" title="These indicators are CI-proxy derived, not production measurements">
        No deployment provider is connected, so every CI workflow run is currently
        counted as a deployment. On the audited repository only 6 of 34 counted
        deployments were deployment-shaped, and lead time collapsed to roughly
        0.1 minutes for every pull request because the matched run was the CI job
        the merge itself triggered. Treat these as pipeline statistics.{" "}
        <Link to="/repositories" style={{ color: "var(--accent)" }}>See data coverage.</Link>
      </Banner>

      {state.status === "loading" && <LoadingState label="Loading delivery metrics" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && state.data.services.length === 0 && (
        <EmptyState
          title="No repositories tracked yet"
          body="Configure GITHUB_REPOS in backend/.env and run a sync to start ingesting delivery activity."
          action={<Link className="button button--primary" to="/repositories">Go to repositories</Link>}
        />
      )}

      {state.status === "success" && state.data.services.length > 0 && (() => {
        const totals = aggregate(state.data.services);
        return (
          <>
            <section className="section">
              <h2 className="section__title">Delivery indicators</h2>
              <div className="metric-grid">
                <MetricCard
                  label="Deployment Frequency"
                  value={totals.frequency}
                  unit="/week"
                  unavailableReason="No workflow run completed inside this window."
                  note={`${totals.deployments} successful runs counted as deployments`}
                />
                <MetricCard
                  label="Change Lead Time"
                  value={totals.leadTime === null ? null : formatHours(totals.leadTime)}
                  unavailableReason="No merged pull request was followed by a successful run in this window."
                  note="Merge to next successful run — not to production."
                />
                <MetricCard
                  label="Change Failure Rate"
                  value={totals.failureRate === null ? null : formatPercent(totals.failureRate)}
                  unavailableReason="No completed runs in this window."
                  note={`${totals.failures} failed of ${totals.deployments + totals.failures} completed runs`}
                  tone={totals.failureRate !== null && totals.failureRate >= 20 ? "danger" : "neutral"}
                  toneLabel={totals.failureRate !== null && totals.failureRate >= 20 ? "Elevated" : undefined}
                />
                <MetricCard
                  label="Recovery Time"
                  value={totals.recovery === null ? null : formatHours(totals.recovery)}
                  unavailableReason="No failure was followed by a success in this window."
                  note="Failed run to next successful run."
                />
              </div>
            </section>

            <section className="section">
              <h2 className="section__title">Not yet measured</h2>
              <p className="section__hint">
                DevPulse reports what it cannot see, rather than defaulting these to zero.
              </p>
              <div className="metric-grid">
                <MetricCard label="Deployment Rework Rate" value={null}
                  unavailableReason="Requires a deployment provider to distinguish planned from incident-driven releases." />
                <MetricCard label="Runtime Health" value={null}
                  unavailableReason="No monitoring provider is connected." />
                <MetricCard label="Primary Bottleneck" value={null}
                  unavailableReason="The bottleneck engine arrives in Stage 9." />
                <MetricCard label="Open Incidents" value={null}
                  unavailableReason="No incident-management provider is connected." />
              </div>
            </section>
          </>
        );
      })()}
    </>
  );
}
