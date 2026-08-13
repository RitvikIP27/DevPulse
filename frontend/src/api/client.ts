export interface ServiceDoraMetrics {
  service: string;
  deployment_frequency_per_week: number;
  lead_time_hours: number | null;
  change_failure_rate_pct: number;
  mttr_hours: number | null;
  total_deployments: number;
  total_failures: number;
}

export interface DoraMetricsResponse {
  window_days: number;
  services: ServiceDoraMetrics[];
}

export async function fetchDoraMetrics(windowDays = 30): Promise<DoraMetricsResponse> {
  const res = await fetch(`/api/metrics/dora?window_days=${windowDays}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch DORA metrics: ${res.status}`);
  }
  return res.json();
}

export async function triggerSync(): Promise<void> {
  const res = await fetch("/api/ingest/sync", { method: "POST" });
  if (!res.ok) {
    throw new Error(`Failed to trigger sync: ${res.status}`);
  }
}
