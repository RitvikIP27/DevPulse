import PlannedPage from "./Planned";

export default function Deliveries() {
  return (
    <PlannedPage
      title="Deliveries"
      description="The lifecycle of a single change, reconstructed across every system it passed through."
      stage="Stage 4"
      body="A delivery trace links a commit to its pull request, CI run, build, deployment, rollout and any incident that followed. DevPulse cannot build one yet, because nothing it ingests currently carries a commit SHA to correlate on."
      requires={[
        "Commit SHA, branch and event captured during ingestion — no join key exists today",
        "A normalized event model so GitHub and future providers produce comparable events (Stage 3)",
        "Correlation rules with recorded evidence, never inferred from timestamp proximity alone (Stage 4)",
      ]}
    />
  );
}
