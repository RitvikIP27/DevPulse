import { useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge from "../components/ui/StatusBadge";
import { ErrorState, LoadingState } from "../components/ui/States";
import {
  createDeploymentRule, deleteDeploymentRule, fetchDeploymentRules, fetchRepositories,
  type DeploymentRuleList, type RepositorySummary,
} from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";

function DeploymentRules({ repository }: { repository: RepositorySummary }) {
  const { state, reload } = useAsync<DeploymentRuleList>(
    () => fetchDeploymentRules(repository.id), [repository.id]
  );
  const [pattern, setPattern] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!pattern.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createDeploymentRule(repository.id, pattern.trim());
      setPattern("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the rule.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(ruleId: number) {
    setBusy(true);
    try {
      await deleteDeploymentRule(repository.id, ruleId);
      reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: "var(--space-4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <strong>{repository.display_name ?? repository.full_name}</strong>
          <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {repository.full_name}
          </div>
        </div>
        {state.status === "success" && (
          <StatusBadge tone={state.data.deployment_source === "NONE" ? "neutral" : "success"}>
            {state.data.deployment_source === "NONE" ? "No deployment source" : state.data.deployment_source}
          </StatusBadge>
        )}
      </div>

      {state.status === "loading" && <LoadingState label="Loading rules" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (
        <>
          {state.data.rules.length > 0 && (
            <table className="data-table" style={{ marginTop: "var(--space-4)" }}>
              <thead>
                <tr><th>Workflow name contains</th><th>Environment</th><th>Matching runs</th><th /></tr>
              </thead>
              <tbody>
                {state.data.rules.map((rule) => (
                  <tr key={rule.id}>
                    <td className="mono">{rule.workflow_name_pattern}</td>
                    <td>{rule.environment}</td>
                    <td className="data-table__numeric">{rule.matched_run_count}</td>
                    <td>
                      <button className="button" disabled={busy} onClick={() => remove(rule.id)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <form onSubmit={add} style={{ display: "flex", gap: 8, marginTop: "var(--space-4)", flexWrap: "wrap" }}>
            <input
              className="select"
              style={{ flex: "1 1 260px", cursor: "text" }}
              placeholder="Workflow name contains, e.g. CD Workflow"
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
              aria-label={`Deployment workflow pattern for ${repository.full_name}`}
            />
            <button className="button button--primary" disabled={busy || !pattern.trim()}>
              Add rule
            </button>
          </form>
          {error && <p style={{ color: "var(--danger)", fontSize: 13 }}>{error}</p>}
        </>
      )}
    </div>
  );
}

function DeploymentRulesSection() {
  const { state, reload } = useAsync(() => fetchRepositories(), []);

  if (state.status === "loading") return <LoadingState label="Loading repositories" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;
  if (state.data.repositories.length === 0) {
    return <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No repositories tracked yet.</p>;
  }

  return (
    <>
      {state.data.repositories.map((repository) => (
        <DeploymentRules key={repository.id} repository={repository} />
      ))}
    </>
  );
}

export default function Settings() {
  const { windowDays, setWindowDays } = useFilters();

  return (
    <>
      <PageHeader
        title="Settings"
        description="How this DevPulse instance is configured."
      />

      <Banner tone="info" title="Configuration is environment-driven for now">
        Tracked repositories and credentials come from <code>backend/.env</code>.
        Managing them from the interface requires repository CRUD and encrypted
        credential storage, which arrive with the integrations model.
      </Banner>

      <section className="section">
        <h2 className="section__title">Deployment mapping</h2>
        <p className="section__hint">
          DevPulse uses a deployment provider where one exists. When none does, name the
          workflow that performs deployment — it is the only way to measure production
          delivery without guessing, and guessing is what inflated the old numbers.
        </p>
        <DeploymentRulesSection />
      </section>

      <section className="section">
        <h2 className="section__title">Analysis window</h2>
        <div className="card">
          <label htmlFor="settings-window" style={{ display: "block", marginBottom: "var(--space-3)", fontSize: 13, color: "var(--text-secondary)" }}>
            Default look-back window used across metric pages.
          </label>
          <select
            id="settings-window"
            className="select"
            value={windowDays}
            onChange={(event) => setWindowDays(Number(event.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </section>

      <section className="section">
        <h2 className="section__title">Environment</h2>
        <div className="card scroll-x">
          <table className="data-table">
            <thead><tr><th>Setting</th><th>Source</th><th>Value</th></tr></thead>
            <tbody>
              <tr><td>Tracked repositories</td><td className="mono">GITHUB_REPOS</td><td style={{ color: "var(--text-muted)" }}>Set in backend/.env</td></tr>
              <tr><td>GitHub credentials</td><td className="mono">GITHUB_TOKEN</td><td style={{ color: "var(--text-muted)" }}>Never displayed</td></tr>
              <tr><td>Database</td><td className="mono">DATABASE_URL</td><td style={{ color: "var(--text-muted)" }}>Never displayed</td></tr>
              <tr><td>Schema</td><td className="mono">alembic</td><td>Migrations applied at container start</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
