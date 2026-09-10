import { useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import StatusBadge, { type BadgeTone } from "../components/ui/StatusBadge";
import Banner from "../components/ui/Banner";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import {
  fetchDeliveries, fetchDelivery,
  type DeliveryDetail, type DeliveryStage, type StageStatus,
} from "../api/client";
import { useAsync } from "../state/useAsync";
import { formatMinutes, formatRelativeDate } from "../format";

const STATUS_TONE: Record<StageStatus, BadgeTone> = {
  SUCCESS: "success",
  FAILED: "danger",
  IN_PROGRESS: "info",
  NOT_OBSERVED: "neutral",
};

const STATUS_LABEL: Record<StageStatus, string> = {
  SUCCESS: "Success",
  FAILED: "Failed",
  IN_PROGRESS: "In progress",
  NOT_OBSERVED: "Not observed",
};

function StageRow({ stage }: { stage: DeliveryStage }) {
  const unobserved = stage.status === "NOT_OBSERVED";
  return (
    <div className={`trace-stage${unobserved ? " trace-stage--unobserved" : ""}`}>
      <span className="trace-stage__name">{stage.stage}</span>

      <span className="trace-stage__rail">
        <span className="trace-stage__line" />
        <span className={`trace-stage__dot trace-stage__dot--${stage.status.toLowerCase()}`} />
      </span>

      <div>
        <StatusBadge tone={STATUS_TONE[stage.status]}>{STATUS_LABEL[stage.status]}</StatusBadge>
        <p className="trace-stage__detail" style={{ marginTop: 6 }}>{stage.detail}</p>
        {stage.runs.length > 0 && (
          <ul className="trace-runs">
            {stage.runs.map((run, index) => (
              <li key={`${run.name}-${index}`}>
                <StatusBadge tone={run.status === "failure" ? "danger" : "success"}>
                  {run.status ?? "unknown"}
                </StatusBadge>
                <span className="trace-runs__name">{run.name}</span>
                {run.url && (
                  <a href={run.url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                    view
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <span className="trace-stage__duration">
        {stage.duration_minutes !== null ? formatMinutes(stage.duration_minutes) : "—"}
      </span>
    </div>
  );
}

function DeliveryTrace({ id, onBack }: { id: string; onBack: () => void }) {
  const { state, reload } = useAsync<DeliveryDetail>(() => fetchDelivery(id), [id]);

  if (state.status === "loading") return <LoadingState label="Loading delivery trace" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const delivery = state.data;
  return (
    <>
      <button className="button" onClick={onBack} style={{ marginBottom: "var(--space-5)" }}>
        ← All deliveries
      </button>

      <PageHeader
        title={`Delivery · PR #${delivery.pull_request_number}`}
        description={delivery.title ?? undefined}
        actions={
          <StatusBadge tone={STATUS_TONE[delivery.status]}>{STATUS_LABEL[delivery.status]}</StatusBadge>
        }
      />

      <div className="evidence-panel">
        <p className="evidence-panel__label">Correlation evidence · {delivery.correlation.confidence} confidence</p>
        <p className="evidence-panel__body">{delivery.correlation.evidence}</p>
      </div>

      <section className="section">
        <h2 className="section__title">Pipeline</h2>
        <p className="section__hint">
          {delivery.stage_count_observed} of {delivery.stage_count_total} stages observed ·
          commit <code>{delivery.commit_sha.slice(0, 10)}</code>
          {delivery.author_login && <> · by {delivery.author_login}</>}
        </p>
        <div className="card">
          <div className="trace">
            {delivery.stages.map((stage) => <StageRow key={stage.stage} stage={stage} />)}
          </div>
        </div>
      </section>
    </>
  );
}

export default function Deliveries() {
  const [selected, setSelected] = useState<string | null>(null);
  const { state, reload } = useAsync(() => fetchDeliveries(), []);

  if (selected) return <DeliveryTrace id={selected} onBack={() => setSelected(null)} />;

  return (
    <>
      <PageHeader
        title="Deliveries"
        description="The lifecycle of a single change, reconstructed across every system that reported it."
      />

      {state.status === "loading" && <LoadingState label="Loading deliveries" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (
        <>
          <Banner tone="info" title="Correlated on commit identity, never on timing">
            A delivery links a merged pull request to every workflow run reporting
            the same merge commit. Records that do not share a commit are left
            unlinked rather than attached to whichever change happened to be
            nearest in time. Deployment, runtime and incident stages have no
            provider connected and are shown as not observed.
          </Banner>

          {state.data.uncorrelatable_count > 0 && (
            <Banner tone="warning" title="Some merged pull requests cannot be correlated">
              {state.data.uncorrelatable_count} merged pull request(s) carry no merge
              commit SHA, because they were ingested before DevPulse captured
              correlation keys. Re-sync the repository to backfill them.
            </Banner>
          )}

          {state.data.deliveries.length === 0 ? (
            <EmptyState
              icon="⇉"
              title="No deliveries reconstructed yet"
              body="A delivery requires a merged pull request with a merge commit. Sync a repository that has merged pull requests to build traces."
            />
          ) : (
            <div className="card scroll-x">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Change</th>
                    <th>Commit</th>
                    <th>Status</th>
                    <th>Total time</th>
                    <th>Stages observed</th>
                    <th>Merged</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.deliveries.map((delivery) => (
                    <tr
                      key={delivery.id}
                      className="delivery-row"
                      onClick={() => setSelected(delivery.id)}
                    >
                      <td>
                        <div className="delivery-row__title">
                          #{delivery.pull_request_number} {delivery.title ?? "Untitled"}
                        </div>
                        <div className="delivery-row__meta">
                          {delivery.service}
                          {delivery.author_login && <> · {delivery.author_login}</>}
                        </div>
                      </td>
                      <td className="mono">{delivery.commit_sha.slice(0, 10)}</td>
                      <td>
                        <StatusBadge tone={STATUS_TONE[delivery.status]}>
                          {STATUS_LABEL[delivery.status]}
                        </StatusBadge>
                      </td>
                      <td className="data-table__numeric">
                        {formatMinutes(delivery.total_duration_minutes)}
                      </td>
                      <td className="data-table__numeric">
                        {delivery.stage_count_observed}/{delivery.stage_count_total}
                      </td>
                      <td>{formatRelativeDate(delivery.completed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
