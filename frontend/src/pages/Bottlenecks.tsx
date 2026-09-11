import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge, { type BadgeTone } from "../components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { fetchBottlenecks, type StageAnalysis } from "../api/client";
import { useAsync } from "../state/useAsync";
import { useFilters } from "../state/FilterContext";
import { formatMinutes, UNAVAILABLE } from "../format";
import AnomalyList from "../components/ui/AnomalyList";

const IMPACT_TONE: Record<StageAnalysis["impact"], BadgeTone> = {
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "neutral",
};

function ScoreBreakdown({ analysis }: { analysis: StageAnalysis }) {
  return (
    <div>
      {analysis.components.map((component) => (
        <div key={component.name} className="component-row">
          <span className="component-row__name">
            {component.name}
            <span className="component-row__weight"> · weight {component.weight}</span>
          </span>
          <span className="component-row__track">
            <span
              className="component-row__fill"
              style={{ width: `${Math.min(100, component.value)}%` }}
            />
          </span>
          <span className="component-row__value">+{component.contribution}</span>
          <p className="component-row__explanation">{component.explanation}</p>
        </div>
      ))}
    </div>
  );
}

function StageCard({ analysis, primary }: { analysis: StageAnalysis; primary?: boolean }) {
  return (
    <div className="card" style={{ marginBottom: "var(--space-5)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>{analysis.stage}</h3>
            <StatusBadge tone={IMPACT_TONE[analysis.impact]}>{analysis.impact} impact</StatusBadge>
            {analysis.is_regression && <StatusBadge tone="danger">Regression</StatusBadge>}
            {primary && <StatusBadge tone="info">Primary bottleneck</StatusBadge>}
          </div>
          <div className="score-hero" style={{ marginTop: 12 }}>
            <span className="score-hero__value">{analysis.score}</span>
            <span className="score-hero__max">/ 100 bottleneck score</span>
          </div>
        </div>

        <div style={{ textAlign: "right", fontSize: 13 }}>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Current median </span>
            <strong>{formatMinutes(analysis.current.median_minutes)}</strong>
          </div>
          <div style={{ marginTop: 4 }}>
            <span style={{ color: "var(--text-muted)" }}>Baseline </span>
            <strong>
              {analysis.baseline.median_minutes === null
                ? UNAVAILABLE
                : formatMinutes(analysis.baseline.median_minutes)}
            </strong>
          </div>
          {analysis.change_pct !== null && (
            <div style={{ marginTop: 4, color: analysis.change_pct > 0 ? "var(--danger)" : "var(--success)" }}>
              {analysis.change_pct > 0 ? "▲" : "▼"} {Math.abs(analysis.change_pct)}%
            </div>
          )}
        </div>
      </div>

      <h4 style={{ fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-6) 0 var(--space-2)" }}>
        Why this score
      </h4>
      <ScoreBreakdown analysis={analysis} />

      <h4 style={{ fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-6) 0 var(--space-2)" }}>
        Evidence
      </h4>
      <ul className="evidence-list">
        {analysis.evidence.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

export default function Bottlenecks() {
  const { windowDays } = useFilters();
  const { state, reload } = useAsync(() => fetchBottlenecks(windowDays), [windowDays]);

  return (
    <>
      <PageHeader
        title="Bottlenecks & Anomalies"
        description="Where delivery time is being spent, and what has changed against its own history."
      />

      <section className="section">
        <h2 className="section__title">Recent anomalies</h2>
        <p className="section__hint">
          Metrics that moved far enough from their own recent baseline to be worth
          attention. Improvements are never reported, and nothing is claimed
          without enough history to compare against.
        </p>
        <AnomalyList windowDays={windowDays} />
      </section>

      <h2 className="section__title" style={{ marginTop: "var(--space-10)" }}>
        Stage bottlenecks
      </h2>

      {state.status === "loading" && <LoadingState label="Analysing delivery stages" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (
        <>
          <Banner tone="info" title="Scored deterministically, not by picking the slowest stage">
            A stage that has always taken twenty minutes is a cost, not a
            constraint. The score combines latency contribution, regression
            against the previous period, failure rate and frequency — each shown
            separately with its weight, so the number can be taken apart. When no
            baseline exists the regression signal is dropped and the remaining
            weights are renormalised, so a stage is never penalised for lacking
            history. No AI is involved.
          </Banner>

          {state.data.unavailable_reason ? (
            <EmptyState
              icon="⧗"
              title="Not enough data to identify a bottleneck"
              body={state.data.unavailable_reason}
            />
          ) : (
            <>
              <p className="section__hint">
                {state.data.deliveries_analysed} deliveries analysed over the last{" "}
                {state.data.window_days} days, compared against the preceding{" "}
                {state.data.window_days} days.
              </p>
              {state.data.stages.map((analysis, index) => (
                <StageCard
                  key={analysis.stage}
                  analysis={analysis}
                  primary={index === 0 && analysis.stage === state.data.primary_bottleneck?.stage}
                />
              ))}
            </>
          )}
        </>
      )}
    </>
  );
}
