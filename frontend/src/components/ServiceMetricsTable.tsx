import type { ServiceDoraMetrics } from "../api/client";

interface Props {
  services: ServiceDoraMetrics[];
}

// Simple thresholding to flag a service as a bottleneck — tune these for your team.
function isBottleneck(s: ServiceDoraMetrics): boolean {
  return s.change_failure_rate_pct >= 20 || (s.lead_time_hours ?? 0) > 48;
}

export default function ServiceMetricsTable({ services }: Props) {
  if (services.length === 0) {
    return <p className="empty-state">No data yet — trigger a sync to ingest GitHub activity.</p>;
  }

  return (
    <table className="metrics-table">
      <thead>
        <tr>
          <th>Service</th>
          <th>Deploy Frequency</th>
          <th>Lead Time</th>
          <th>Change Failure Rate</th>
          <th>MTTR</th>
        </tr>
      </thead>
      <tbody>
        {services.map((s) => (
          <tr key={s.service} className={isBottleneck(s) ? "row-bottleneck" : ""}>
            <td>
              {s.service}
              {isBottleneck(s) && <span className="bottleneck-badge">bottleneck</span>}
            </td>
            <td>{s.deployment_frequency_per_week}/week</td>
            <td>{s.lead_time_hours != null ? `${s.lead_time_hours} hrs` : "—"}</td>
            <td>{s.change_failure_rate_pct}%</td>
            <td>{s.mttr_hours != null ? `${s.mttr_hours} hrs` : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
