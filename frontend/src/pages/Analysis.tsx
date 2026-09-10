import { useState } from "react";
import PageHeader from "../components/ui/PageHeader";
import Banner from "../components/ui/Banner";
import StatusBadge, { type BadgeTone } from "../components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import {
  fetchAnalysisCandidates, fetchEvidence, requestRca,
  type EvidencePackage, type RcaConfidence, type RcaResponse, type RcaResult,
} from "../api/client";
import { useAsync } from "../state/useAsync";
import { formatMinutes, formatRelativeDate } from "../format";

const CONFIDENCE_TONE: Record<RcaConfidence, BadgeTone> = {
  HIGH: "success",
  MEDIUM: "warning",
  LOW: "neutral",
  INSUFFICIENT: "danger",
};

function List({ title, items, muted }: { title: string; items: string[]; muted?: boolean }) {
  if (items.length === 0) return null;
  return (
    <>
      <h4 style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-5) 0 var(--space-2)" }}>
        {title}
      </h4>
      <ul className="evidence-list">
        {items.map((item) => (
          <li key={item} style={muted ? { color: "var(--text-muted)" } : undefined}>{item}</li>
        ))}
      </ul>
    </>
  );
}

function EvidenceView({ evidence }: { evidence: EvidencePackage }) {
  return (
    <div className="card" style={{ marginBottom: "var(--space-5)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <strong style={{ fontSize: 14 }}>Evidence package</strong>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
          {evidence.evidence_hash}
        </span>
      </div>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>
        Assembled deterministically from delivery traces, baselines, bottleneck
        scoring, runtime comparison and coverage. This is the complete set of
        facts any analysis is allowed to use.
      </p>

      <table className="data-table" style={{ marginTop: "var(--space-4)" }}>
        <thead><tr><th>Stage</th><th>Status</th><th>Duration</th></tr></thead>
        <tbody>
          {evidence.stages.map((stage) => (
            <tr key={stage.stage}>
              <td style={{ fontWeight: 600 }}>{stage.stage}</td>
              <td style={{ color: stage.status === "NOT_OBSERVED" ? "var(--text-muted)" : undefined }}>
                {stage.status}
              </td>
              <td className="data-table__numeric">{formatMinutes(stage.duration_minutes)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: "flex", gap: 8, marginTop: "var(--space-4)", flexWrap: "wrap" }}>
        <StatusBadge tone="neutral">Coverage: {evidence.coverage.confidence}</StatusBadge>
        {evidence.conflicts.length > 0 && (
          <StatusBadge tone="danger">{evidence.conflicts.length} conflict(s)</StatusBadge>
        )}
        {evidence.incidents.length > 0 && (
          <StatusBadge tone="warning">{evidence.incidents.length} incident(s)</StatusBadge>
        )}
      </div>

      <List title="Known limitations of this evidence" items={evidence.known_limitations} muted />
    </div>
  );
}

function RcaView({ rca }: { rca: RcaResponse }) {
  if (!rca.available || !rca.result) {
    return (
      <Banner tone="warning" title="AI analysis is not available">
        {rca.unavailable_reason}
      </Banner>
    );
  }

  const result: RcaResult = rca.result;
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <strong style={{ fontSize: 14 }}>Analysis</strong>
          <StatusBadge tone={CONFIDENCE_TONE[result.confidence]}>
            {result.confidence} confidence
          </StatusBadge>
          {rca.cached && <StatusBadge tone="neutral">Cached</StatusBadge>}
        </div>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          {rca.model} · {rca.prompt_version}
        </span>
      </div>

      {rca.integrity_warnings.length > 0 && (
        <div style={{ marginTop: "var(--space-4)" }}>
          <Banner tone="warning" title="Some figures could not be traced to the evidence">
            {rca.integrity_warnings.join(" ")}
          </Banner>
        </div>
      )}

      <p style={{ fontSize: 14, marginTop: "var(--space-4)" }}>{result.summary}</p>

      <h4 style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-5) 0 var(--space-2)" }}>
        Likely cause
      </h4>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>{result.likely_cause}</p>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>
        <strong>Impact:</strong> {result.impact}
      </p>

      {/* Observed and inferred are shown separately on purpose. */}
      <List title="Observed facts" items={result.observed_facts} />
      <List title="Inferences drawn" items={result.inferences} />

      {result.alternative_hypotheses.length > 0 && (
        <>
          <h4 style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", margin: "var(--space-5) 0 var(--space-2)" }}>
            Alternative hypotheses
          </h4>
          {result.alternative_hypotheses.map((hypothesis) => (
            <div key={hypothesis.hypothesis} style={{ marginBottom: "var(--space-3)" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 13 }}>{hypothesis.hypothesis}</span>
                <StatusBadge tone={CONFIDENCE_TONE[hypothesis.confidence]}>
                  {hypothesis.confidence}
                </StatusBadge>
              </div>
              <ul className="evidence-list" style={{ marginTop: 6 }}>
                {hypothesis.supporting_evidence.map((item) => <li key={item}>{item}</li>)}
                {hypothesis.contradicting_evidence.map((item) => (
                  <li key={item} style={{ color: "var(--text-muted)" }}>Against: {item}</li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      <List title="Recommended investigation" items={result.recommended_investigation} />
      <List title="Recommended actions" items={result.recommended_actions} />
      <List title="Not determined" items={result.unknowns} muted />
    </div>
  );
}

function Detail({ deploymentId, onBack }: { deploymentId: number; onBack: () => void }) {
  const { state, reload } = useAsync<EvidencePackage>(() => fetchEvidence(deploymentId), [deploymentId]);
  const [rca, setRca] = useState<RcaResponse | null>(null);
  const [running, setRunning] = useState(false);

  async function run(force = false) {
    setRunning(true);
    try {
      setRca(await requestRca(deploymentId, force));
    } finally {
      setRunning(false);
    }
  }

  if (state.status === "loading") return <LoadingState label="Loading evidence" />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={reload} />;

  const evidence = state.data;
  return (
    <>
      <button className="button" onClick={onBack} style={{ marginBottom: "var(--space-5)" }}>
        ← All candidates
      </button>

      <PageHeader
        title={`Analysis · deployment ${evidence.deployment_id}`}
        description={evidence.pull_request_title ?? evidence.repository_full_name}
        actions={
          <button className="button button--primary" onClick={() => run(rca !== null)} disabled={running}>
            {running ? "Analysing…" : rca ? "Re-run analysis" : "Run analysis"}
          </button>
        }
      />

      <EvidenceView evidence={evidence} />
      {rca && <RcaView rca={rca} />}
    </>
  );
}

export default function Analysis() {
  const [selected, setSelected] = useState<number | null>(null);
  const { state, reload } = useAsync(() => fetchAnalysisCandidates(), []);

  if (selected !== null) {
    return <Detail deploymentId={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <>
      <PageHeader
        title="Analysis"
        description="Evidence-backed root-cause analysis over deterministically established facts."
      />

      {state.status === "loading" && <LoadingState label="Loading candidates" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={reload} />}

      {state.status === "success" && (
        <>
          <Banner tone="info" title="AI reasons over evidence; it never gathers it">
            Every fact is established by the deterministic pipeline first — traces,
            baselines, bottleneck scores, runtime comparison, coverage. The model
            receives that package and nothing else: no database access, no logs, no
            provider APIs. Its output separates observed facts from inferences, is
            checked for figures that do not appear in the evidence, and is stored
            with the exact evidence that produced it.
          </Banner>

          {state.data.candidates.length === 0 ? (
            <EmptyState
              icon="✦"
              title="No deployments to analyse"
              body="Analysis operates on production deployments. Configure a deployment source so DevPulse can identify them."
            />
          ) : (
            <div className="card scroll-x">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Deployment</th><th>Status</th><th>Conflicts</th>
                    <th>Incidents</th><th>Coverage</th><th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.candidates.map((candidate) => (
                    <tr
                      key={candidate.deployment_id}
                      className="delivery-row"
                      onClick={() => setSelected(candidate.deployment_id)}
                    >
                      <td>
                        <div style={{ fontWeight: 600 }}>{candidate.service}</div>
                        <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                          {candidate.commit_sha?.slice(0, 10) ?? "—"} · {candidate.environment}
                        </div>
                      </td>
                      <td>
                        <StatusBadge tone={candidate.deployment_status === "SUCCESS" ? "success" : "danger"}>
                          {candidate.deployment_status}
                        </StatusBadge>
                      </td>
                      <td>
                        {candidate.conflict_count > 0
                          ? <StatusBadge tone="danger">{candidate.conflict_count}</StatusBadge>
                          : <span className="data-table__unavailable">—</span>}
                      </td>
                      <td className="data-table__numeric">{candidate.incident_count || "—"}</td>
                      <td>
                        <StatusBadge tone="neutral">{candidate.coverage_confidence}</StatusBadge>
                      </td>
                      <td>{formatRelativeDate(candidate.deployed_at)}</td>
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
