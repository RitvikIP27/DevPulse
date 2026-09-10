import { useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import StatusBadge, { type BadgeTone } from "../components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import {
  fetchRepositories, triggerSync,
  type AnalysisConfidence, type CoverageStatus, type RepositorySummary,
} from "../api/client";
import { useAsync } from "../state/useAsync";
import { formatRelativeDate } from "../format";

const CONFIDENCE_TONE: Record<AnalysisConfidence, BadgeTone> = {
  HIGH: "success",
  LIMITED: "warning",
  MINIMAL: "danger",
};

const STATUS_TONE: Record<CoverageStatus, BadgeTone> = {
  AVAILABLE: "success",
  NO_DATA: "warning",
  NOT_CONFIGURED: "neutral",
};

const STATUS_LABEL: Record<CoverageStatus, string> = {
  AVAILABLE: "Available",
  NO_DATA: "No data",
  NOT_CONFIGURED: "Not configured",
};

function CoveragePanel({ repository }: { repository: RepositorySummary }) {
  return (
    <div className="card" style={{ marginTop: "var(--space-4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)", gap: 12, flexWrap: "wrap" }}>
        <strong style={{ fontSize: 13 }}>Pipeline data coverage</strong>
        <StatusBadge tone={CONFIDENCE_TONE[repository.coverage.confidence]}>
          {repository.coverage.confidence} confidence
        </StatusBadge>
      </div>

      <div className="coverage-list">
        {repository.coverage.stages.map((stage) => (
          <div key={stage.stage} className="coverage-row" title={stage.detail}>
            <span className="coverage-row__stage">{stage.stage}</span>
            <span className="coverage-row__track">
              <span className={`coverage-row__fill coverage-row__fill--${stage.status.toLowerCase().replace("_", "-")}`} />
            </span>
            <StatusBadge tone={STATUS_TONE[stage.status]}>
              {STATUS_LABEL[stage.status]}
              {stage.record_count !== null && stage.record_count > 0 ? ` · ${stage.record_count}` : ""}
            </StatusBadge>
          </div>
        ))}
      </div>

      <p className="coverage-detail">{repository.coverage.confidence_reason}</p>
    </div>
  );
}

export default function Repositories() {
  const { state, reload } = useAsync(() => fetchRepositories(), []);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  async function handleSync() {
    setSyncing(true);
    setSyncNote(null);
    try {
      await triggerSync();
      // The API returns before ingestion finishes and reports no completion
      // signal, so the wording must not imply the sync has succeeded.
      setSyncNote("Sync requested. Ingestion runs in the background — refresh in a moment.");
    } catch (error) {
      setSyncNote(error instanceof Error ? error.message : "Could not start sync.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Repositories"
        description="Tracked repositories and exactly which delivery stages DevPulse can see for each."
        actions={
          <button className="button button--primary" onClick={handleSync} disabled={syncing}>
            {syncing ? "Starting…" : "Sync from GitHub"}
          </button>
        }
      />

      {syncNote && (
        <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: -16, marginBottom: 24 }}>
          {syncNote}{" "}
          <button className="button" style={{ padding: "3px 10px", marginLeft: 6 }} onClick={reload}>
            Refresh
          </button>
        </p>
      )}

      {state.status === "loading" && <LoadingState label="Loading repositories" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && state.data.repositories.length === 0 && (
        <EmptyState
          icon="◫"
          title="No repositories tracked"
          body="Set GITHUB_REPOS in backend/.env to a comma-separated list of owner/repo, restart the backend, then run a sync."
        />
      )}

      {state.status === "success" && state.data.repositories.length > 0 && (
        <div className="card scroll-x">
          <table className="data-table">
            <thead>
              <tr>
                <th>Repository</th>
                <th>Pull requests</th>
                <th>Workflow runs</th>
                <th>Last activity</th>
                <th>Confidence</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {state.data.repositories.map((repository) => (
                <tr key={repository.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{repository.display_name ?? repository.full_name}</div>
                    <div className="mono" style={{ color: "var(--text-muted)", fontSize: 12 }}>
                      {repository.full_name}
                    </div>
                    {expanded === repository.id && <CoveragePanel repository={repository} />}
                  </td>
                  <td className="data-table__numeric">{repository.pull_request_count}</td>
                  <td className="data-table__numeric">{repository.workflow_run_count}</td>
                  <td>{formatRelativeDate(repository.last_activity_at)}</td>
                  <td>
                    <StatusBadge tone={CONFIDENCE_TONE[repository.coverage.confidence]}>
                      {repository.coverage.confidence}
                    </StatusBadge>
                  </td>
                  <td>
                    <button
                      className="button"
                      aria-expanded={expanded === repository.id}
                      onClick={() => setExpanded(expanded === repository.id ? null : repository.id)}
                    >
                      {expanded === repository.id ? "Hide coverage" : "Coverage"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
