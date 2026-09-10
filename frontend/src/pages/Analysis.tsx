import PlannedPage from "./Planned";

export default function Analysis() {
  return (
    <PlannedPage
      title="Analysis"
      description="Evidence-backed root-cause analysis and recommendations."
      stage="Stage 16"
      body="AI reasoning is deliberately deferred until the deterministic evidence pipeline is complete. An AI given incomplete, uncorrelated data would produce confident explanations that nothing supports — which is precisely the failure this product exists to avoid."
      requires={[
        "Delivery traces, baselines, anomalies and conflicts to reason over (Stages 4 through 12)",
        "A structured evidence package assembled deterministically before any model is called (Stage 15)",
        "Confidence and unknowns reported alongside every conclusion, per ADR-008 and ADR-011",
      ]}
    />
  );
}
