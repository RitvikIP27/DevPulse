import { useState } from "react";
import StatusBadge, { type BadgeTone } from "./StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "./States";
import { acknowledgeAnomaly, fetchAnomalies, type Anomaly } from "../../api/client";
import { useAsync } from "../../state/useAsync";
import { formatMinutes } from "../../format";

const SEVERITY_TONE: Record<Anomaly["severity"], BadgeTone> = {
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "neutral",
};

/** Duration metrics read better as minutes; rates are percentages. */
function formatValue(metric: string, value: number): string {
  return metric.endsWith("_pct") ? `${value.toFixed(1)}%` : formatMinutes(value);
}

function AnomalyCard({ anomaly, onAcknowledge }: { anomaly: Anomaly; onAcknowledge: () => void }) {
  const [busy, setBusy] = useState(false);

  async function handle() {
    setBusy(true);
    try {
      await acknowledgeAnomaly(anomaly.id);
      onAcknowledge();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="card"
      style={{ marginBottom: "var(--space-4)", opacity: anomaly.acknowledged_at ? 0.6 : 1 }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <strong style={{ fontSize: 14 }}>{anomaly.metric.replace(/_/g, " ")}</strong>
          <StatusBadge tone={SEVERITY_TONE[anomaly.severity]}>{anomaly.severity}</StatusBadge>
          {anomaly.stage && <StatusBadge tone="neutral">{anomaly.stage}</StatusBadge>}
          {anomaly.acknowledged_at && <StatusBadge tone="neutral">Acknowledged</StatusBadge>}
        </div>
        {!anomaly.acknowledged_at && (
          <button className="button" onClick={handle} disabled={busy}>
            {busy ? "…" : "Acknowledge"}
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: 24, marginTop: "var(--space-4)", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em" }}>BASELINE</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {formatValue(anomaly.metric, anomaly.baseline_value)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em" }}>CURRENT</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>
            {formatValue(anomaly.metric, anomaly.current_value)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em" }}>CHANGE</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--danger)" }}>
            {anomaly.change_pct > 0 ? "+" : ""}{anomaly.change_pct}%
          </div>
        </div>
      </div>

      <ul className="evidence-list" style={{ marginTop: "var(--space-4)" }}>
        {anomaly.evidence.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

export default function AnomalyList({ windowDays }: { windowDays: number }) {
  const { state, reload } = useAsync(() => fetchAnomalies(windowDays), [windowDays]);

  if (state.status === "loading") return <LoadingState label="Detecting anomalies" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  if (state.data.anomalies.length === 0) {
    return (
      <EmptyState
        icon="◷"
        title="No anomalies detected"
        body={state.data.unavailable_reason ?? "Every metric is within its normal range."}
      />
    );
  }

  return (
    <>
      {state.data.anomalies.map((anomaly) => (
        <AnomalyCard key={anomaly.id} anomaly={anomaly} onAcknowledge={reload} />
      ))}
    </>
  );
}
