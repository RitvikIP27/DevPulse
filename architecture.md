# DevPulse — Architecture

## 1. System Overview

DevPulse is a multi-system engineering intelligence platform.

Core flow:

```text
External Engineering Systems
        ↓
Connector Layer
        ↓
Raw Provider Data
        ↓
Normalization
        ↓
Normalized Delivery Events
        ↓
Correlation
        ↓
Delivery Traces
        ↓
Analytics
        ↓
Historical Baselines
        ↓
Bottlenecks / Anomalies / Conflicts
        ↓
Evidence Package
        ↓
Future AI Reasoning
```

AI is intentionally outside the deterministic core.

---

# 2. System Components

```text
Frontend
   ↓
FastAPI API
   ↓
Domain Services
   ↓
PostgreSQL

External systems
   ↓
Connectors
   ↓
Ingestion / Normalization
   ↓
PostgreSQL
```

---

# 3. Backend Layers

Recommended conceptual structure:

```text
backend/app/
├── api/
├── core/
├── models/
├── schemas/
├── services/
│   ├── ingestion/
│   ├── normalization/
│   ├── correlation/
│   ├── analytics/
│   ├── health/
│   └── analysis/
└── connectors/
    ├── github/
    ├── github_actions/
    ├── kubernetes/
    ├── argocd/
    ├── prometheus/
    └── pagerduty/
```

The actual structure may differ during incremental migration.

---

# 4. Architectural Patterns

## Adapter Pattern

Every external provider gets an adapter.

```text
Provider API
   ↓
Adapter
   ↓
DevPulse interface
```

## Service Layer

Business logic lives outside routes.

Routes should be thin.

```text
HTTP request
 ↓
Route
 ↓
Service
 ↓
Repository/database
```

## Domain Model

Analytics should operate on DevPulse concepts rather than vendor schemas.

## Event-Based Model

Delivery lifecycle state is represented as events.

## Evidence-First Analysis

Analytics produce evidence structures that future AI can consume.

---

# 5. Data Flow

Example:

```text
GitHub PR
 ↓
GitHub Connector
 ↓
Raw PR
 ↓
PR Normalizer
 ↓
PR_MERGED event
 ↓
Correlation
 ↓
Delivery #183
```

GitHub Actions:

```text
Workflow run
 ↓
Actions Connector
 ↓
CI Normalizer
 ↓
CI_COMPLETED event
 ↓
Correlation by commit SHA
 ↓
Delivery #183
```

ArgoCD:

```text
Sync
 ↓
ArgoCD Connector
 ↓
DEPLOYMENT_COMPLETED
 ↓
Correlation by revision
 ↓
Delivery #183
```

---

# 6. Database Domain Model

The target conceptual model is:

```text
Repository
    │
    └── Service
           │
           └── Pipeline
                  │
                  ├── PipelineStage
                  │
                  └── Delivery
                         │
                         ├── DeliveryEvent
                         ├── PullRequest
                         ├── Commit
                         ├── CI Run
                         ├── Build
                         ├── Artifact
                         ├── Deployment
                         ├── RuntimeObservation
                         └── Incident
```

Supporting entities:

```text
Integration
MetricSnapshot
Anomaly
Bottleneck
SyncJob
RcaAnalysis
Recommendation
```

Do not create every entity in one migration. Introduce them as features require.

---

# 7. Important Entity Responsibilities

## Repository

Source-control repository identity.

## Service

Logical deployable/application unit.

## Integration

Connection to an external provider.

## Pipeline

A delivery process associated with a service.

## PipelineStage

Logical stage in the pipeline.

## Delivery

One change moving through the system.

## DeliveryEvent

Normalized event from any provider.

## Deployment

Actual deployment into an environment.

## RuntimeObservation

Runtime health measurement.

## Incident

Operational incident associated with a service/time window.

## MetricSnapshot

Historical metric state.

## Bottleneck

Deterministically identified delivery constraint.

## Anomaly

Detected deviation from baseline.

---

# 8. Correlation Strategy

Strong correlation keys:

```text
commit SHA
deployment revision
artifact digest
workflow run ID
PR number
service
repository
environment
application
```

Secondary signals:

```text
branch
timestamp
release identifier
```

A correlation should retain its basis.

Conceptually:

```text
Correlation
------------
source_event
target_event
method
confidence
evidence
```

---

# 9. API Design

Use resource-oriented REST APIs.

Examples:

```text
GET  /api/repositories
POST /api/repositories
DELETE /api/repositories/{id}

POST /api/repositories/{id}/sync

GET /api/deliveries
GET /api/deliveries/{id}

GET /api/metrics/dora
GET /api/metrics/trends

GET /api/bottlenecks
GET /api/anomalies

GET /api/integrations
POST /api/integrations
DELETE /api/integrations/{id}
```

Use query parameters for filtering:

```text
?service_id=
?repository_id=
?environment=
?window_days=
?from=
?to=
```

Keep routes thin.

Use Pydantic schemas for API contracts.

---

# 10. API Response Principles

Responses should be:

- predictable
- typed
- explicit
- versionable where necessary

Missing data should be represented explicitly.

Example:

```json
{
  "metric": "deployment_frequency",
  "value": null,
  "status": "unavailable",
  "reason": "Production deployment integration not configured"
}
```

---

# 11. Error Model

External connector errors should distinguish:

```text
AUTHENTICATION_ERROR
AUTHORIZATION_ERROR
RATE_LIMIT
NOT_FOUND
TIMEOUT
PROVIDER_ERROR
VALIDATION_ERROR
PARTIAL_SYNC
```

Persist sync state where useful.

---

# 12. Sync Model

Initial:

```text
Manual sync
 ↓
background task
 ↓
fetch
 ↓
normalize
 ↓
persist
```

Future:

```text
Webhook
+
Scheduled sync
+
Historical backfill
+
Incremental sync
```

---

# 13. Deterministic Analytics Architecture

Analytics should operate on normalized domain data.

```text
Delivery traces
      ↓
Metric calculators
      ↓
Historical comparison
      ↓
Anomaly engine
      ↓
Bottleneck engine
      ↓
Conflict engine
      ↓
Evidence builder
```

---

# 14. Future AI Boundary

AI must receive an evidence package:

```text
facts
metrics
baselines
anomalies
correlations
conflicts
coverage
```

AI must not directly define the source-of-truth event timeline.

---

# 15. Infrastructure

Current:

```text
React
FastAPI
PostgreSQL
Docker Compose
```

Future:

```text
Kubernetes
background workers
managed database
observability
secret management
```

Avoid premature distributed systems.
