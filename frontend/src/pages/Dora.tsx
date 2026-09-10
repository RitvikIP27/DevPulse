import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge from "../components/ui/StatusBadge";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { fetchDoraMetrics, type ServiceDoraMetrics } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";
import { formatHours, formatPercent, UNAVAILABLE } from "../format";
import { Link } from "react-router-dom";

const ELEVATED_FAILURE_RATE_PCT = 20;

const SOURCE_LABEL: Record<ServiceDoraMetrics["deployment_source"], string> = {
  GITHUB_DEPLOYMENTS: "GitHub Deployments",
  CONFIGURED_WORKFLOW: "Configured workflow",
  NONE: "No deployment source",
};

function ServiceMetrics({ service }: { service: ServiceDoraMetrics }) {
  const measurable = service.deployment_source !== "NONE";

  return (
    <section className="section">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "var(--space-4)", flexWrap: "wrap" }}>
        <h2 className="section__title" style={{ margin: 0 }}>{service.service}</h2>
        <StatusBadge tone={measurable ? "info" : "neutral"}>
          {SOURCE_LABEL[service.deployment_source]}
        </StatusBadge>
      </div>

      {service.unavailable_reason && (
        <Banner tone="warning" title="Deployment-derived metrics are unavailable">
          {service.unavailable_reason}{" "}
          {!measurable && <Link to="/settings" style={{ color: "var(--accent)" }}>Configure a deployment workflow.</Link>}
        </Banner>
      )}

      <div className="metric-grid">
        <MetricCard
          label="Deployment Frequency"
          value={service.deployment_frequency_per_week}
          unit="/week"
          unavailableReason="Requires identified production deployments."
          note={`${service.total_deployments} production deployment(s)`}
        />
        <MetricCard
          label="Change Lead Time"
          value={service.lead_time_hours === null ? null : formatHours(service.lead_time_hours)}
          unavailableReason="No deployed commit could be matched to a merged pull request."
          note="Merge to the deployment that shipped that commit."
        />
        <MetricCard
          label="Change Fail Rate"
          value={service.change_failure_rate_pct === null ? null : formatPercent(service.change_failure_rate_pct)}
          unavailableReason="Requires concluded production deployments."
          note={`${service.total_failures} failed of ${service.total_deployments + service.total_failures}`}
          tone={
            service.change_failure_rate_pct !== null &&
            service.change_failure_rate_pct >= ELEVATED_FAILURE_RATE_PCT
              ? "danger" : undefined
          }
          toneLabel={
            service.change_failure_rate_pct !== null &&
            service.change_failure_rate_pct >= ELEVATED_FAILURE_RATE_PCT
              ? "Elevated" : undefined
          }
        />
        <MetricCard
          label="Failed Deployment Recovery"
          value={
            service.failed_deployment_recovery_hours === null
              ? null : formatHours(service.failed_deployment_recovery_hours)
          }
          unavailableReason="No failed production deployment was followed by a recovery."
          note="Failed deployment to the next successful one."
        />
        <MetricCard
          label="Deployment Rework Rate"
          value={
            service.deployment_rework_rate_pct === null
              ? null : formatPercent(service.deployment_rework_rate_pct)
          }
          unavailableReason="Requires production deployments."
          note="Deployments that remediated a previous failure. Lower bound without incident data."
        />
      </div>
    </section>
  );
}

export default function Dora() {
  const { windowDays } = useFilters();
  const { state, reload } = useAsync(() => fetchDoraMetrics(windowDays), [windowDays]);

  return (
    <>
      <PageHeader
        title="DORA"
        description="The five current DORA delivery metrics, computed from production deployments."
      />

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
          <Banner tone="info" title="Metrics come from deployments, never from CI runs">
            DevPulse identifies production deployments from a deployment provider
            where one exists, or from a workflow you explicitly designate. A
            successful CI run is not treated as a deployment: doing so previously
            overstated deployment frequency by roughly 5.7× and collapsed lead
            time to about 0.1 minutes per pull request. Where no deployment
            source exists, metrics report as unavailable rather than as zero.
          </Banner>

          <div className="card scroll-x" style={{ marginBottom: "var(--space-10)" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Service</th><th>Source</th><th>Frequency</th><th>Lead time</th>
                  <th>Fail rate</th><th>Recovery</th><th>Rework</th>
                </tr>
              </thead>
              <tbody>
                {state.data.services.map((service) => (
                  <tr key={service.service}>
                    <td style={{ fontWeight: 600 }}>{service.service}</td>
                    <td>
                      <StatusBadge tone={service.deployment_source === "NONE" ? "neutral" : "info"}>
                        {SOURCE_LABEL[service.deployment_source]}
                      </StatusBadge>
                    </td>
                    <td className="data-table__numeric">
                      {service.deployment_frequency_per_week === null
                        ? <span className="data-table__unavailable">{UNAVAILABLE}</span>
                        : `${service.deployment_frequency_per_week}/wk`}
                    </td>
                    <td className="data-table__numeric">{formatHours(service.lead_time_hours)}</td>
                    <td className="data-table__numeric">{formatPercent(service.change_failure_rate_pct)}</td>
                    <td className="data-table__numeric">{formatHours(service.failed_deployment_recovery_hours)}</td>
                    <td className="data-table__numeric">{formatPercent(service.deployment_rework_rate_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {state.data.services.map((service) => (
            <ServiceMetrics key={service.service} service={service} />
          ))}
        </>
      )}
    </>
  );
}
