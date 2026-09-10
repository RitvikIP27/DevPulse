import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge from "../components/ui/StatusBadge";
import MetricCard from "../components/ui/MetricCard";
import { EmptyState, ErrorState, LoadingState, NotYetAvailable } from "../components/ui/States";
import { fetchConflicts, type Conflict, type DeploymentConflictReport } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";

function ConflictCard({ conflict }: { conflict: Conflict }) {
  return (
    <div className="card" style={{ borderColor: "#4a2331", marginTop: "var(--space-4)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <strong style={{ fontSize: 14 }}>{conflict.title}</strong>
        {/* Never "caused": temporal proximity is evidence, not proof. */}
        <StatusBadge tone={conflict.strength === "CORRELATED" ? "danger" : "warning"}>
          {conflict.strength.replace("_", " ")}
        </StatusBadge>
      </div>

      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>
        {conflict.description}
      </p>

      <h5 style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-5) 0 var(--space-2)" }}>
        Evidence
      </h5>
      <ul className="evidence-list">
        {conflict.evidence.map((item) => <li key={item}>{item}</li>)}
      </ul>

      <h5 style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-5) 0 var(--space-2)" }}>
        Not determined
      </h5>
      <ul className="evidence-list">
        {conflict.unknowns.map((item) => (
          <li key={item} style={{ color: "var(--text-muted)" }}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function ReportCard({ report }: { report: DeploymentConflictReport }) {
  return (
    <div className="card" style={{ marginBottom: "var(--space-5)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <strong style={{ fontSize: 14 }}>
            Deployment to {report.environment}
          </strong>
          <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            {report.repository_full_name}
            {report.commit_sha && <> · {report.commit_sha.slice(0, 10)}</>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
          <StatusBadge tone={report.deployment_status === "SUCCESS" ? "success" : "danger"}>
            Control plane: {report.deployment_status}
          </StatusBadge>
          {report.runtime.available ? (
            <StatusBadge tone={report.conflicts.length > 0 ? "danger" : "success"}>
              Runtime: {report.conflicts.length > 0 ? "Degraded" : "Stable"}
            </StatusBadge>
          ) : (
            <StatusBadge tone="neutral">Runtime: Not observed</StatusBadge>
          )}
          {report.incidents_after > 0 && (
            <StatusBadge tone="warning">{report.incidents_after} incident(s)</StatusBadge>
          )}
        </div>
      </div>

      {report.runtime.available && report.runtime.shifts.length > 0 && (
        <table className="data-table" style={{ marginTop: "var(--space-4)" }}>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Before</th>
              <th>After</th>
              <th>Change</th>
              <th>Samples</th>
            </tr>
          </thead>
          <tbody>
            {report.runtime.shifts.map((shift) => (
              <tr key={shift.metric}>
                <td className="mono">{shift.metric}</td>
                <td className="data-table__numeric">{shift.before_value ?? "—"}</td>
                <td className="data-table__numeric">{shift.after_value ?? "—"}</td>
                <td
                  className="data-table__numeric"
                  style={{ color: shift.is_degradation ? "var(--danger)" : "var(--text-secondary)" }}
                >
                  {shift.change_pct === null ? "—" : `${shift.change_pct > 0 ? "+" : ""}${shift.change_pct}%`}
                </td>
                <td className="data-table__numeric" style={{ color: "var(--text-muted)" }}>
                  {shift.sample_count_before} / {shift.sample_count_after}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!report.runtime.available && (
        <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: "var(--space-4)" }}>
          {report.runtime.unavailable_reason}
        </p>
      )}

      {report.conflicts.map((conflict) => (
        <ConflictCard key={conflict.type} conflict={conflict} />
      ))}
    </div>
  );
}

export default function Health() {
  const { windowDays } = useFilters();
  const { state, reload } = useAsync(() => fetchConflicts(windowDays), [windowDays]);

  return (
    <>
      <PageHeader
        title="Runtime Health"
        description="Whether production stayed healthy after each deployment, and where systems disagree."
      />

      {state.status === "loading" && <LoadingState label="Analysing runtime health" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (
        <>
          <Banner tone="info" title="Control-plane success is not application health">
            A deployment platform reporting SUCCESS is describing its own rollout
            mechanism, not the health of the application it shipped. DevPulse
            compares runtime metrics before and after each deployment and reports
            when the two disagree — as a correlation with its evidence and its
            unknowns, never as a cause.
          </Banner>

          <section className="section">
            <h2 className="section__title">Provider coverage</h2>
            <div className="metric-grid">
              <MetricCard
                label="Monitoring"
                value={state.data.runtime_available ? "Connected" : null}
                unavailableReason="Set PROMETHEUS_URL to compare runtime health around deployments."
              />
              <MetricCard
                label="Incidents"
                value={state.data.incidents_available ? "Connected" : null}
                unavailableReason="Set PAGERDUTY_TOKEN and PAGERDUTY_SERVICE_IDS to correlate incidents."
              />
              <MetricCard
                label="Conflicts detected"
                value={
                  state.data.runtime_available || state.data.incidents_available
                    ? state.data.conflict_count
                    : null
                }
                unavailableReason="Needs a monitoring or incident provider."
                tone={state.data.conflict_count > 0 ? "danger" : undefined}
                toneLabel={state.data.conflict_count > 0 ? "Attention" : undefined}
              />
            </div>
          </section>

          {state.data.unavailable_reason && (
            <EmptyState
              icon="◎"
              title="Runtime health cannot be determined"
              body={state.data.unavailable_reason}
            />
          )}

          {state.data.reports.length > 0 && (
            <section className="section">
              <h2 className="section__title">Deployments</h2>
              {state.data.reports.map((report) => (
                <ReportCard key={report.deployment_id} report={report} />
              ))}
            </section>
          )}

          <section className="section">
            <h2 className="section__title">Composite health score</h2>
            <NotYetAvailable
              title="Engineering health scoring is not available yet"
              body="A composite score is only meaningful if every dimension can be explained from an underlying measurement. Delivery and reliability dimensions exist, but observability and runtime scoring need sustained runtime data first."
              stage="Stage 18"
            />
          </section>
        </>
      )}
    </>
  );
}
