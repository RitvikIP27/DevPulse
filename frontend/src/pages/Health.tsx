import PlannedPage from "./Planned";

export default function Health() {
  return (
    <PlannedPage
      title="Engineering Health"
      description="Composite delivery, reliability, runtime and observability scores."
      stage="Stage 18"
      body="A health score is only meaningful if every component can be explained from an underlying measurement. Runtime, reliability and observability have no data source connected, so a score computed today would be an arbitrary number wearing a percentage sign."
      requires={[
        "Runtime telemetry to score anything beyond the pipeline (Stage 13)",
        "Incident data for a reliability dimension (Stage 14)",
        "A documented formula per dimension, so every score can be traced back to its inputs",
      ]}
    />
  );
}
