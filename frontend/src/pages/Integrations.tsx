import PageHeader from "../components/ui/PageHeader";
import StatusBadge from "../components/ui/StatusBadge";
import { ErrorState, LoadingState } from "../components/ui/States";
import { fetchRepositories } from "../api/client";
import { useAsync } from "../state/useAsync";

interface IntegrationRow {
  name: string;
  category: string;
  connected: boolean;
  note: string;
}

export default function Integrations() {
  // Connection state is inferred from what has actually been ingested rather
  // than from a hard-coded list, so the page cannot claim a provider is
  // connected when nothing has come from it.
  const { state, reload } = useAsync(() => fetchRepositories(), []);

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Providers DevPulse can currently collect from, and what remains unconnected."
      />

      {state.status === "loading" && <LoadingState label="Loading integrations" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (() => {
        const repositories = state.data.repositories;
        const pullRequests = repositories.reduce((n, r) => n + r.pull_request_count, 0);
        const runs = repositories.reduce((n, r) => n + r.workflow_run_count, 0);

        const rows: IntegrationRow[] = [
          { name: "GitHub", category: "Source control", connected: pullRequests > 0,
            note: pullRequests > 0
              ? `${pullRequests} pull requests across ${repositories.length} repositories`
              : "Configured, but nothing ingested yet" },
          { name: "GitHub Actions", category: "CI", connected: runs > 0,
            note: runs > 0 ? `${runs} workflow runs ingested` : "Configured, but nothing ingested yet" },
          { name: "ArgoCD", category: "Deployment", connected: false, note: "No connector implemented" },
          { name: "Kubernetes", category: "Runtime", connected: false, note: "No connector implemented" },
          { name: "Prometheus", category: "Monitoring", connected: false, note: "No connector implemented" },
          { name: "PagerDuty", category: "Incidents", connected: false, note: "No connector implemented" },
          { name: "SonarQube", category: "Quality", connected: false, note: "No connector implemented" },
          { name: "Jenkins", category: "CI", connected: false, note: "No connector implemented" },
        ];

        return (
          <div className="card scroll-x">
            <table className="data-table">
              <thead>
                <tr><th>Provider</th><th>Stage</th><th>Status</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.name}>
                    <td style={{ fontWeight: 600 }}>{row.name}</td>
                    <td style={{ color: "var(--text-secondary)" }}>{row.category}</td>
                    <td>
                      <StatusBadge tone={row.connected ? "success" : "neutral"}>
                        {row.connected ? "Connected" : "Not configured"}
                      </StatusBadge>
                    </td>
                    <td style={{ color: "var(--text-muted)" }}>{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}
    </>
  );
}
