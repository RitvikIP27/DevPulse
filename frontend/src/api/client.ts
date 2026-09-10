/** Central API client. Every network call goes through here (rules.md 14). */

const BASE = "/api";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    // fetch only rejects on network-level failure, which for this app almost
    // always means the API container is not running.
    throw new ApiError("Could not reach the DevPulse API.", 0);
  }
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed.`, response.status);
  }
  return response.json() as Promise<T>;
}

/* ---------------------------------- DORA --------------------------------- */

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

export function fetchDoraMetrics(windowDays = 30): Promise<DoraMetricsResponse> {
  return request<DoraMetricsResponse>(`/metrics/dora?window_days=${windowDays}`);
}

/* ------------------------------ Repositories ----------------------------- */

export type PipelineStage =
  | "SOURCE" | "REVIEW" | "CI" | "QUALITY" | "BUILD"
  | "ARTIFACT" | "DEPLOYMENT" | "ROLLOUT" | "RUNTIME" | "INCIDENT";

export type CoverageStatus = "AVAILABLE" | "NO_DATA" | "NOT_CONFIGURED";
export type AnalysisConfidence = "HIGH" | "LIMITED" | "MINIMAL";

export interface StageCoverage {
  stage: PipelineStage;
  status: CoverageStatus;
  detail: string;
  record_count: number | null;
}

export interface RepositoryCoverage {
  stages: StageCoverage[];
  confidence: AnalysisConfidence;
  confidence_reason: string;
}

export interface RepositorySummary {
  id: number;
  full_name: string;
  display_name: string | null;
  pull_request_count: number;
  workflow_run_count: number;
  last_activity_at: string | null;
  coverage: RepositoryCoverage;
}

export function fetchRepositories(): Promise<{ repositories: RepositorySummary[] }> {
  return request<{ repositories: RepositorySummary[] }>("/repositories");
}

/* --------------------------------- Ingest -------------------------------- */

export async function triggerSync(): Promise<void> {
  const response = await fetch(`${BASE}/ingest/sync`, { method: "POST" });
  if (!response.ok) {
    throw new ApiError("Failed to start sync.", response.status);
  }
}
