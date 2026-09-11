/** Central API client. Every network call goes through here (rules.md 14). */

const BASE = "/api";
const TOKEN_KEY = "devpulse.token";

/** The token lives in localStorage so a refresh does not sign the user out. */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Private browsing can deny storage. The session still works; it just will
    // not survive a reload, which is better than failing to sign in at all.
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  } catch {
    // fetch only rejects on network-level failure, which for this app almost
    // always means the API container is not running.
    throw new ApiError("Could not reach the DevPulse API.", 0);
  }
  if (response.status === 401) {
    // The token is gone or expired. Clearing it makes the shell fall back to
    // the login screen instead of looping on failed requests.
    setToken(null);
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed.`, response.status);
  }
  return response.json() as Promise<T>;
}

/* ---------------------------------- DORA --------------------------------- */

export type DeploymentSource = "GITHUB_DEPLOYMENTS" | "CONFIGURED_WORKFLOW" | "NONE";

export interface ServiceDoraMetrics {
  service: string;
  deployment_source: DeploymentSource;
  unavailable_reason: string | null;
  deployment_frequency_per_week: number | null;
  lead_time_hours: number | null;
  change_failure_rate_pct: number | null;
  failed_deployment_recovery_hours: number | null;
  deployment_rework_rate_pct: number | null;
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

export interface LastSync {
  status: "RUNNING" | "SUCCESS" | "PARTIAL" | "FAILED";
  started_at: string;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface RepositorySummary {
  id: number;
  full_name: string;
  display_name: string | null;
  pull_request_count: number;
  workflow_run_count: number;
  last_activity_at: string | null;
  last_sync: LastSync | null;
  correlatable_run_pct: number | null;
  coverage: RepositoryCoverage;
}

export function fetchRepositories(): Promise<{ repositories: RepositorySummary[] }> {
  return request<{ repositories: RepositorySummary[] }>("/repositories");
}

/* --------------------------------- Ingest -------------------------------- */

export async function triggerSync(): Promise<void> {
  const response = await fetch(`${BASE}/ingest/sync`, { method: "POST", headers: authHeaders() });
  if (!response.ok) {
    throw new ApiError("Failed to start sync.", response.status);
  }
}

export interface SyncJob {
  id: number;
  repository_full_name: string | null;
  provider: string;
  status: "RUNNING" | "SUCCESS" | "PARTIAL" | "FAILED";
  started_at: string;
  finished_at: string | null;
  pull_requests_written: number;
  workflow_runs_written: number;
  error_code: string | null;
  error_message: string | null;
}

export function fetchSyncJobs(limit = 20): Promise<{ jobs: SyncJob[] }> {
  return request<{ jobs: SyncJob[] }>(`/ingest/jobs?limit=${limit}`);
}

/* ------------------------------- Deliveries ------------------------------ */

export type StageStatus = "SUCCESS" | "FAILED" | "IN_PROGRESS" | "NOT_OBSERVED";

export interface StageRun {
  name: string;
  status: string | null;
  started_at: string | null;
  completed_at: string | null;
  url: string | null;
  provider: string;
}

export interface DeliveryStage {
  stage: PipelineStage;
  status: StageStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_minutes: number | null;
  provider: string | null;
  detail: string;
  runs: StageRun[];
}

export interface DeliverySummary {
  id: string;
  repository_full_name: string;
  service: string;
  commit_sha: string;
  pull_request_number: number;
  title: string | null;
  author_login: string | null;
  started_at: string;
  completed_at: string | null;
  total_duration_minutes: number | null;
  status: StageStatus;
  stage_count_observed: number;
  stage_count_total: number;
}

export interface DeliveryDetail extends DeliverySummary {
  stages: DeliveryStage[];
  correlation: {
    method: string;
    confidence: "HIGH" | "MEDIUM" | "LOW";
    evidence: string;
    commit_sha: string;
  };
}

export function fetchDeliveries(limit = 25): Promise<{
  deliveries: DeliverySummary[];
  uncorrelatable_count: number;
}> {
  return request(`/deliveries?limit=${limit}`);
}

export function fetchDelivery(id: string): Promise<DeliveryDetail> {
  return request<DeliveryDetail>(`/deliveries/${id}`);
}

/* ---------------------------- Deployment rules --------------------------- */

export interface DeploymentRule {
  id: number;
  repository_id: number;
  workflow_name_pattern: string;
  environment: string;
  is_production: boolean;
  matched_run_count: number;
}

export interface DeploymentRuleList {
  rules: DeploymentRule[];
  deployment_source: DeploymentSource;
}

export function fetchDeploymentRules(repositoryId: number): Promise<DeploymentRuleList> {
  return request<DeploymentRuleList>(`/repositories/${repositoryId}/deployment-rules`);
}

export async function createDeploymentRule(
  repositoryId: number,
  workflowNamePattern: string,
  environment = "production"
): Promise<DeploymentRuleList> {
  const response = await fetch(`${BASE}/repositories/${repositoryId}/deployment-rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      workflow_name_pattern: workflowNamePattern,
      environment,
      is_production: true,
    }),
  });
  if (!response.ok) {
    throw new ApiError(
      response.status === 409
        ? "That rule already exists."
        : "Could not create the deployment rule.",
      response.status
    );
  }
  return response.json() as Promise<DeploymentRuleList>;
}

export async function deleteDeploymentRule(repositoryId: number, ruleId: number): Promise<void> {
  const response = await fetch(`${BASE}/repositories/${repositoryId}/deployment-rules/${ruleId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError("Could not remove the deployment rule.", response.status);
  }
}

/* ------------------------------- Bottlenecks ----------------------------- */

export interface ScoreComponent {
  name: string;
  value: number;
  weight: number;
  contribution: number;
  explanation: string;
}

export interface StageBaseline {
  sample_count: number;
  median_minutes: number | null;
  p90_minutes: number | null;
}

export interface StageAnalysis {
  stage: PipelineStage;
  score: number;
  impact: "HIGH" | "MEDIUM" | "LOW";
  current: StageBaseline;
  baseline: StageBaseline;
  change_pct: number | null;
  is_regression: boolean;
  latency_contribution_pct: number;
  failure_rate_pct: number;
  affected_deliveries: number;
  total_deliveries: number;
  components: ScoreComponent[];
  evidence: string[];
}

export interface BottleneckResponse {
  window_days: number;
  deliveries_analysed: number;
  primary_bottleneck: StageAnalysis | null;
  stages: StageAnalysis[];
  unavailable_reason: string | null;
}

export function fetchBottlenecks(windowDays = 30): Promise<BottleneckResponse> {
  return request<BottleneckResponse>(`/bottlenecks?window_days=${windowDays}`);
}

/* -------------------------------- Conflicts ------------------------------ */

export interface MetricShift {
  metric: string;
  before_value: number | null;
  after_value: number | null;
  change_pct: number | null;
  sample_count_before: number;
  sample_count_after: number;
  is_degradation: boolean;
}

export interface RuntimeComparison {
  available: boolean;
  unavailable_reason: string | null;
  window_minutes: number;
  shifts: MetricShift[];
}

export interface Conflict {
  type: string;
  strength: "CORRELATED" | "POTENTIALLY_RELATED";
  title: string;
  description: string;
  evidence: string[];
  unknowns: string[];
}

export interface DeploymentConflictReport {
  deployment_id: number;
  repository_full_name: string;
  environment: string;
  commit_sha: string | null;
  deployment_status: string;
  deployed_at: string;
  runtime: RuntimeComparison;
  incidents_after: number;
  conflicts: Conflict[];
}

export interface ConflictListResponse {
  reports: DeploymentConflictReport[];
  conflict_count: number;
  runtime_available: boolean;
  incidents_available: boolean;
  unavailable_reason: string | null;
}

export function fetchConflicts(windowDays = 30): Promise<ConflictListResponse> {
  return request<ConflictListResponse>(`/conflicts?window_days=${windowDays}`);
}

/* -------------------------------- Analysis ------------------------------- */

export interface AnalysisCandidate {
  deployment_id: number;
  repository_full_name: string;
  service: string;
  environment: string;
  commit_sha: string | null;
  deployment_status: string;
  deployed_at: string;
  conflict_count: number;
  incident_count: number;
  coverage_confidence: AnalysisConfidence;
}

export interface EvidenceStage {
  stage: PipelineStage;
  status: string;
  duration_minutes: number | null;
  detail: string;
}

export interface EvidencePackage {
  evidence_hash: string;
  generated_at: string;
  repository_full_name: string;
  service: string;
  deployment_id: number;
  environment: string;
  commit_sha: string | null;
  deployment_status: string;
  deployed_at: string;
  pull_request_number: number | null;
  pull_request_title: string | null;
  author_login: string | null;
  stages: EvidenceStage[];
  bottlenecks: StageAnalysis[];
  runtime: RuntimeComparison;
  incidents: {
    title: string | null;
    status: string;
    started_at: string;
    resolved_at: string | null;
    minutes_after_deployment: number | null;
  }[];
  conflicts: Conflict[];
  coverage: {
    confidence: AnalysisConfidence;
    confidence_reason: string;
    observed_stages: PipelineStage[];
    unobserved_stages: PipelineStage[];
  };
  known_limitations: string[];
}

export type RcaConfidence = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";

export interface Hypothesis {
  hypothesis: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  confidence: RcaConfidence;
}

export interface RcaResult {
  summary: string;
  likely_cause: string;
  confidence: RcaConfidence;
  affected_stage: string | null;
  impact: string;
  observed_facts: string[];
  inferences: string[];
  alternative_hypotheses: Hypothesis[];
  recommended_investigation: string[];
  recommended_actions: string[];
  unknowns: string[];
}

export interface RcaResponse {
  available: boolean;
  unavailable_reason: string | null;
  evidence_hash: string | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  generated_at: string | null;
  cached: boolean;
  result: RcaResult | null;
  integrity_warnings: string[];
}

export function fetchAnalysisCandidates(): Promise<{ candidates: AnalysisCandidate[] }> {
  return request<{ candidates: AnalysisCandidate[] }>("/analysis/candidates");
}

export function fetchEvidence(deploymentId: number): Promise<EvidencePackage> {
  return request<EvidencePackage>(`/analysis/evidence/${deploymentId}`);
}

export async function requestRca(deploymentId: number, force = false): Promise<RcaResponse> {
  const response = await fetch(`${BASE}/analysis/rca/${deploymentId}?force=${force}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError("Could not run the analysis.", response.status);
  }
  return response.json() as Promise<RcaResponse>;
}

/* -------------------------------- Anomalies ------------------------------ */

export interface Anomaly {
  id: number;
  repository_full_name: string;
  metric: string;
  stage: string | null;
  direction: "INCREASE" | "DECREASE";
  severity: "HIGH" | "MEDIUM" | "LOW";
  current_value: number;
  baseline_value: number;
  change_pct: number;
  sample_count: number;
  baseline_sample_count: number;
  window_start: string;
  window_end: string;
  detected_at: string;
  acknowledged_at: string | null;
  evidence: string[];
}

export interface AnomalyListResponse {
  anomalies: Anomaly[];
  window_days: number;
  detected_now: number;
  unavailable_reason: string | null;
}

export function fetchAnomalies(windowDays = 7): Promise<AnomalyListResponse> {
  return request<AnomalyListResponse>(`/anomalies?window_days=${windowDays}`);
}

export async function acknowledgeAnomaly(id: number): Promise<void> {
  const response = await fetch(`${BASE}/anomalies/${id}/acknowledge`, {
    method: "POST", headers: authHeaders(),
  });
  if (!response.ok) {
    throw new ApiError("Could not acknowledge the anomaly.", response.status);
  }
}

/* ------------------------------ Health score ----------------------------- */

export type HealthDimensionName =
  | "DELIVERY" | "STABILITY" | "PIPELINE" | "RUNTIME" | "OBSERVABILITY";

export interface DimensionInput {
  label: string;
  value: number | null;
  unit: string | null;
  points: number | null;
  max_points: number;
  explanation: string;
}

export interface DimensionScore {
  dimension: HealthDimensionName;
  score: number | null;
  coverage_pct: number;
  unavailable_reason: string | null;
  inputs: DimensionInput[];
}

export interface ServiceHealth {
  service: string;
  repository_full_name: string;
  overall_score: number | null;
  dimensions_scored: number;
  dimensions_total: number;
  unavailable_reason: string | null;
  dimensions: DimensionScore[];
}

export function fetchHealthScore(windowDays = 30): Promise<{
  window_days: number;
  services: ServiceHealth[];
}> {
  return request(`/health-score?window_days=${windowDays}`);
}

/* ----------------------------- Authentication ---------------------------- */

export interface AuthStatus {
  auth_required: boolean;
  has_users: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

export function fetchAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/auth/status");
}

async function submitCredentials(
  path: "login" | "register",
  email: string,
  password: string
): Promise<TokenResponse> {
  const response = await fetch(`${BASE}/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    let detail = path === "login" ? "Incorrect email or password." : "Could not create the account.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // A non-JSON error body is not worth surfacing raw.
    }
    throw new ApiError(detail, response.status);
  }
  const token = (await response.json()) as TokenResponse;
  setToken(token.access_token);
  return token;
}

export const login = (email: string, password: string) =>
  submitCredentials("login", email, password);

export const register = (email: string, password: string) =>
  submitCredentials("register", email, password);

export function logout(): void {
  setToken(null);
}
