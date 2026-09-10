import PageHeader from "../components/ui/PageHeader";
import MetricCard from "../components/ui/MetricCard";
import Banner from "../components/ui/Banner";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { fetchDoraMetrics, type ServiceDoraMetrics } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";
import { formatHours, formatPercent } from "../format";
import { Link } from "react-router-dom";

/** Aggregates per-service rows into one delivery picture.
 *
 * Only services with an identified deployment source contribute. A service
 * DevPulse cannot measure must not dilute an average into looking healthy.
 */
function aggregate(services: ServiceDoraMetrics[]) {
  const measurable = services.filter((s) => s.deployment_source !== "NONE");
  const deployments = measurable.reduce((sum, s) => sum + s.total_deployments, 0);
  const failures = measurable.reduce((sum, s) => sum + s.total_failures, 0);
  const frequency = measurable.reduce((sum, s) => sum + (s.deployment_frequency_per_week ?? 0), 0);

  const mean = (values: number[]) =>
    values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const collect = (pick: (s: ServiceDoraMetrics) => number | null) =>
    measurable.map(pick).filter((v): v is number => v !== null);

  const concluded = deployments + failures;

  return {
    measurableCount: measurable.length,
    unmeasurableCount: services.length - measurable.length,
    deployments,
    failures,
    frequency: measurable.length ? Number(frequency.toFixed(2)) : null,
    failureRate: concluded > 0 ? (failures / concluded) * 100 : null,
    leadTime: mean(collect((s) => s.lead_time_hours)),
    recovery: mean(collect((s) => s.failed_deployment_recovery_hours)),
    rework: mean(collect((s) => s.deployment_rework_rate_pct)),
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
            {totals.unmeasurableCount > 0 && (
              <Banner tone="warning" title="Not every service can be measured">
                {totals.unmeasurableCount} of {state.data.services.length} tracked
                service(s) have no deployment provider connected and no deployment
                workflow configured, so DevPulse cannot identify their production
                deployments. They are excluded from these figures rather than
                counted as zero.{" "}
                <Link to="/settings" style={{ color: "var(--accent)" }}>Configure deployment mapping.</Link>
              </Banner>
            )}

            <section className="section">
              <h2 className="section__title">Delivery performance</h2>
              <p className="section__hint">
                The five current DORA metrics, computed from production deployments
                across {totals.measurableCount} measurable service(s).
              </p>
              <div className="metric-grid">
                <MetricCard
                  label="Deployment Frequency"
                  value={totals.frequency}
                  unit="/week"
                  unavailableReason="No service has an identified deployment source."
                  note={`${totals.deployments} production deployment(s)`}
                />
                <MetricCard
                  label="Change Lead Time"
                  value={totals.leadTime === null ? null : formatHours(totals.leadTime)}
                  unavailableReason="No deployed commit could be matched to a merged pull request."
                  note="Merge to the deployment that shipped that commit."
                />
                <MetricCard
                  label="Change Fail Rate"
                  value={totals.failureRate === null ? null : formatPercent(totals.failureRate)}
                  unavailableReason="No concluded production deployments in this window."
                  note={`${totals.failures} failed of ${totals.deployments + totals.failures}`}
                  tone={totals.failureRate !== null && totals.failureRate >= 20 ? "danger" : undefined}
                  toneLabel={totals.failureRate !== null && totals.failureRate >= 20 ? "Elevated" : undefined}
                />
                <MetricCard
                  label="Failed Deployment Recovery"
                  value={totals.recovery === null ? null : formatHours(totals.recovery)}
                  unavailableReason="No failed production deployment was followed by a recovery."
                  note="Failed deployment to the next successful one."
                />
                <MetricCard
                  label="Deployment Rework Rate"
                  value={totals.rework === null ? null : formatPercent(totals.rework)}
                  unavailableReason="Requires production deployments."
                  note="Deployments remediating a previous failure."
                />
              </div>
            </section>

            <section className="section">
              <h2 className="section__title">Not yet measured</h2>
              <p className="section__hint">
                DevPulse reports what it cannot see, rather than defaulting these to zero.
              </p>
              <div className="metric-grid">
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
