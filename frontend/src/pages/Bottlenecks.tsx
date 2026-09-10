import PlannedPage from "./Planned";

export default function Bottlenecks() {
  return (
    <PlannedPage
      title="Bottlenecks"
      description="Where delivery time is actually being spent, with the evidence behind the claim."
      stage="Stage 9"
      body="Identifying a bottleneck requires per-stage durations across many deliveries and a historical baseline to compare against. DevPulse currently stores neither, so any bottleneck shown here would be guesswork."
      requires={[
        "Delivery traces with per-stage timings (Stage 4)",
        "Rolling historical baselines — median and percentile, not averages (Stage 8)",
        "A transparent scoring model combining latency contribution, regression, queue pressure and failure impact",
      ]}
    />
  );
}
