# DevPulse — Product Requirements Document

**Status:** Active Product Blueprint  
**Version:** 1.0  
**Product:** DevPulse  
**Category:** Engineering Intelligence / Software Delivery Observability  
**Current phase:** Deterministic data, correlation, analytics and validation; AI intentionally deferred

---

## 1. Problem Statement

Modern software delivery pipelines are distributed across many systems.

A single production change can move through:

```text
Developer
  ↓
GitHub / GitLab
  ↓
Code Review
  ↓
CI
  ↓
Quality / Security
  ↓
Build
  ↓
Artifact Registry
  ↓
CD / ArgoCD / Jenkins
  ↓
Kubernetes / Cloud
  ↓
Runtime Monitoring
  ↓
Incident Management
```

Each tool knows only part of the story.

A Git provider knows about commits and pull requests.  
A CI system knows about builds and tests.  
A deployment platform knows about releases.  
Kubernetes knows about rollout state.  
Monitoring knows about runtime health.  
Incident management knows about production incidents.

The engineering problem is therefore not simply collecting metrics.

The problem is:

> **Reconstructing the complete delivery lifecycle of a software change across heterogeneous systems and using that evidence to identify where delivery is slow, unreliable, abnormal, or operationally risky.**

DevPulse exists to create that unified view.

### Product thesis

DevPulse should answer:

- What changed?
- Where is the change now?
- Which pipeline stages did it pass through?
- How long did each stage take?
- Where is the bottleneck?
- What has regressed compared with historical behavior?
- Which deployments failed?
- Did a deployment correlate with runtime degradation?
- Which systems agree or disagree about system health?
- How complete is the available evidence?
- What should an engineer investigate next?

The initial system must answer these questions through deterministic logic.

AI is a future reasoning layer, not the source of truth.

---

# 2. Core Features

## 2.1 Multi-System Integrations

DevPulse must use a connector architecture rather than hard-code analytics against one vendor.

Initial integrations:

- GitHub
- GitHub Actions

Progressive integrations:

- Kubernetes
- ArgoCD
- Prometheus
- PagerDuty
- Jenkins
- GitLab CI
- Additional providers through adapters

Each integration must support, where applicable:

- authentication
- pagination
- incremental synchronization
- historical backfill
- rate-limit handling
- retries
- source identifiers
- sync status
- normalized events

---

## 2.2 Normalized Event Model

External systems expose different schemas.

DevPulse converts them into a common event vocabulary.

Examples:

```text
COMMIT_CREATED
PR_OPENED
PR_REVIEW_REQUESTED
PR_REVIEWED
PR_APPROVED
PR_MERGED

CI_STARTED
CI_COMPLETED
CI_FAILED

QUALITY_CHECK_STARTED
QUALITY_CHECK_COMPLETED
QUALITY_CHECK_FAILED

BUILD_STARTED
BUILD_COMPLETED
BUILD_FAILED

ARTIFACT_CREATED

DEPLOYMENT_STARTED
DEPLOYMENT_COMPLETED
DEPLOYMENT_FAILED
DEPLOYMENT_ROLLED_BACK

ROLLOUT_STARTED
ROLLOUT_COMPLETED
ROLLOUT_FAILED

RUNTIME_DEGRADED
RUNTIME_RECOVERED

INCIDENT_STARTED
INCIDENT_RESOLVED
```

Normalized events must preserve useful provider metadata.

---

## 2.3 Cross-System Correlation

DevPulse must correlate records belonging to the same delivery.

Correlation signals may include:

- commit SHA
- PR number
- repository
- branch
- workflow/run ID
- artifact/image tag
- image digest
- deployment revision
- service/application
- environment
- release identifier
- timestamps

Timestamp proximity alone must not establish causality.

The output is a **Delivery Trace**.

Example:

```text
PR #482
  ↓
commit abc123
  ↓
CI run #18291
  ↓
build
  ↓
artifact
  ↓
deployment
  ↓
Kubernetes rollout
  ↓
runtime observation
  ↓
incident
```

---

## 2.4 Delivery Trace

A delivery is a first-class domain object representing one change moving through the engineering system.

A delivery may contain:

- commit
- pull request
- reviews
- CI runs
- quality checks
- build
- artifact
- deployment
- rollout
- runtime observations
- incidents
- recovery actions

DevPulse must expose delivery traces through APIs and the UI.

---

## 2.5 Pipeline Mapping

DevPulse must represent logical pipeline stages independently of vendor names.

Logical stages:

```text
SOURCE
REVIEW
CI
QUALITY
BUILD
ARTIFACT
DEPLOYMENT
ROLLOUT
RUNTIME
INCIDENT
```

Users can map integrations to these stages.

Example:

```text
Source       → GitHub
CI           → GitHub Actions
Quality      → SonarQube
Artifact     → ECR
Deployment   → ArgoCD
Runtime      → Kubernetes
Monitoring   → Prometheus
Incidents    → PagerDuty
```

Partial pipelines are valid.

---

## 2.6 Data Coverage

DevPulse must explicitly report what data is available.

Example:

```text
Source Control       100%
CI                   100%
Deployment            85%
Runtime                0%
Incidents              0%
```

Incomplete telemetry must reduce analysis confidence.

The product must never silently invent unavailable data.

---

## 2.7 DORA Analytics

DevPulse must support the current five DORA software delivery performance metrics:

1. Change Lead Time
2. Deployment Frequency
3. Failed Deployment Recovery Time
4. Change Fail Rate
5. Deployment Rework Rate

Metrics must be derived from delivery/deployment data where available.

A successful CI workflow must not automatically be treated as a production deployment when actual deployment data exists.

Unavailable metrics should be represented as unavailable rather than fabricated.

---

## 2.8 Historical Analytics

DevPulse must retain historical delivery data and calculate baselines.

Supported analysis:

- rolling windows
- median
- percentiles
- period-over-period comparison
- historical baselines
- trend detection
- regression detection
- failure-rate changes
- latency changes

Example:

```text
Current CI median:       24m
30-day baseline:          7m
Regression:             +243%
```

---

## 2.9 Deterministic Bottleneck Detection

Before AI exists, DevPulse must identify bottlenecks using hard logic.

Signals may include:

- queue time
- execution time
- contribution to delivery time
- failure rate
- retry rate
- historical regression
- throughput
- frequency
- affected deliveries
- operational impact

A bottleneck result must expose evidence.

Example:

```text
Primary Bottleneck: Code Review

Current median:        312m
Historical median:      42m
Regression:           +643%
Affected deliveries: 18/27
Latency contribution: 71%
```

---

## 2.10 Deterministic Anomaly Detection

Detect meaningful deviations such as:

- CI duration spikes
- review queue growth
- deployment failure spikes
- recovery-time regression
- deployment frequency changes
- runtime error spikes
- rollback increases

Every anomaly must include:

- metric
- current value
- baseline
- deviation
- time window
- severity
- evidence

---

## 2.11 Cross-System Conflict Detection

DevPulse must identify contradictory signals.

Example:

```text
ArgoCD:       deployment SUCCESS
Kubernetes:   rollout SUCCESS
Prometheus:   error rate +1600%
PagerDuty:    incident
```

DevPulse should report:

> Deployment control-plane success conflicts with runtime health degradation.

This is an evidence signal, not an automatic root-cause claim.

---

## 2.12 Runtime Correlation

Where runtime telemetry exists, compare:

```text
before deployment
vs
after deployment
```

Potential signals:

- error rate
- latency
- availability
- CPU
- memory
- restarts

Temporal correlation must not automatically be treated as causality.

---

## 2.13 Incident Correlation

Correlate:

```text
deployment
  ↓
runtime degradation
  ↓
incident
  ↓
remediation
  ↓
recovery
```

This enables more meaningful failed-deployment recovery analysis.

---

## 2.14 Engineering Health

Create transparent health dimensions for:

- delivery
- CI
- deployment
- runtime
- reliability
- observability

Every score must be explainable from underlying measurements.

---

## 2.15 Delivery and Analysis UI

Primary navigation:

```text
Overview
Repositories
DORA
Deliveries
Bottlenecks
Health
Analysis
Integrations
Settings
```

The UI must support:

- repository selection
- service selection
- date ranges
- delivery drill-down
- bottleneck drill-down
- anomaly details
- integration status
- data coverage
- loading/error/empty states

---

# 3. Future Features

These features are intentionally later-stage.

## 3.1 AI RCA

AI receives a structured evidence package and produces:

- likely cause
- alternative hypotheses
- supporting evidence
- confidence
- affected stage
- impact
- recommended investigation
- unknowns

AI must not invent telemetry.

---

## 3.2 AI Recommendations

Recommendations should be evidence-backed and specific.

Bad:

> Improve your CI/CD pipeline.

Good:

> Integration tests account for 71% of CI duration and have increased from 4m to 18m. Investigate parallelization and the slowest test groups.

---

## 3.3 AI Provider Abstraction

Create an `AIProvider` abstraction so the platform is not permanently tied to one LLM provider.

---

## 3.4 Automatic Pipeline Discovery

Future discovery may detect:

- GitHub Actions
- deployments
- Kubernetes applications
- ArgoCD applications
- artifact registries
- monitoring integrations

Explicit configuration remains the first implementation.

---

## 3.5 Webhooks / Real-Time Ingestion

Support:

- GitHub webhooks
- deployment events
- runtime events
- incident events

while retaining historical backfill.

---

## 3.6 Scheduled Background Sync

Add worker infrastructure when scale requires it.

Possible future technologies:

- Celery
- Redis
- queue systems

Do not introduce them prematurely.

---

## 3.7 Authentication and Multi-Tenancy

Future support:

```text
Organization
  ↓
Project
  ↓
Service
  ↓
Repository
  ↓
Pipeline
```

Potential features:

- GitHub OAuth/App
- role-based access
- organization management
- multiple services
- multiple repositories

---

## 3.8 Advanced Analytics

Potential future features:

- delivery forecasting
- anomaly clustering
- recurring failure signatures
- service comparison
- team-level analysis
- deployment risk scoring
- change-risk prediction
- intervention effectiveness

---

## 3.9 Production Platform

Future capabilities:

- Kubernetes deployment
- cloud deployment
- managed PostgreSQL
- observability for DevPulse itself
- distributed workers
- scalable ingestion
- secret management
- audit logs

---

# 4. Tech Stack and Constraints

## Current Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

### Frontend

- React
- TypeScript
- Vite

### Infrastructure

- Docker
- Docker Compose
- Kubernetes manifests

### External APIs

- GitHub REST API initially

---

## Future Technologies

Potential:

- Kubernetes
- ArgoCD
- Prometheus
- PagerDuty
- Jenkins
- GitLab CI
- LLM provider abstraction

Only introduce a technology when the product has a concrete requirement for it.

---

## Architecture Constraints

### Constraint 1 — Deterministic first

All core data collection, correlation, DORA, historical analysis, bottleneck detection and anomaly detection must work without AI.

### Constraint 2 — Provider independence

Analytics must not depend on GitHub-specific structures.

### Constraint 3 — Evidence before inference

Every insight must be traceable to data.

### Constraint 4 — Missing data is explicit

Never fabricate production deployment, runtime or incident data.

### Constraint 5 — Incremental architecture

Do not prematurely introduce microservices, queues, Kafka or distributed infrastructure.

### Constraint 6 — Security

Never commit:

- API tokens
- passwords
- cloud credentials
- LLM keys
- database secrets

### Constraint 7 — Backward compatibility

Existing working MVP functionality should be preserved while the architecture evolves.

### Constraint 8 — Testability

Every important analytical rule must have deterministic tests.

### Constraint 9 — Explainability

Every score, bottleneck and anomaly must expose its underlying evidence.

---

# 5. Success Metrics and Validation

## Product Success

DevPulse is successful when it can reconstruct a delivery across multiple systems:

```text
PR
 ↓
Commit
 ↓
CI
 ↓
Build
 ↓
Artifact
 ↓
Deployment
 ↓
Rollout
 ↓
Runtime
 ↓
Incident
```

and identify the state and timing of each stage.

---

## Analytical Success

The system must correctly calculate known ground-truth scenarios.

Example:

```text
Commit:                 10:00
Production deployment:  11:15

Expected lead time:      75m
```

Expected DevPulse result:

```text
75m
```

Another:

```text
Deployment failed:      12:00
Recovery:               12:30

Expected recovery:       30m
```

---

## Bottleneck Validation

Given:

```text
Review:       312m
CI:             8m
Build:          2m
Deployment:     3m
```

DevPulse should identify review as the dominant bottleneck and expose the evidence.

---

## Conflict Validation

Given:

```text
Deployment: SUCCESS
Kubernetes: SUCCESS
Runtime: DEGRADED
Incident: YES
```

DevPulse should identify a deployment/runtime conflict.

It should not incorrectly report the deployment as completely healthy.

---

## Missing Data Validation

If monitoring is unavailable:

```text
Runtime: unavailable
```

DevPulse must reduce analysis coverage and explicitly state the limitation.

---

## Synthetic Pipeline

Maintain a dedicated `devpulse-demo-pipeline` repository containing:

- FastAPI application
- Docker
- GitHub Actions
- Kubernetes

Scenarios:

1. Healthy delivery
2. Slow review
3. Slow CI
4. Failed CI
5. Failed deployment
6. Rollback
7. Runtime regression
8. Deployment/runtime conflict
9. Missing telemetry

---

## Real-World Validation

After synthetic validation, test against real public repositories.

Measure:

- ingestion success
- synchronization reliability
- event normalization accuracy
- correlation accuracy
- coverage
- false positives
- false negatives
- analytical correctness

Never claim production-level metrics when the source data does not support them.

---

## Engineering Success

Every major milestone must:

1. Be implemented.
2. Be tested.
3. Be manually verified.
4. Be documented.
5. Be committed.
6. Be pushed.
7. Be represented by a coherent PR.

The project should demonstrate continuous engineering progress through its Git history.

---

# Definition of Done

DevPulse is considered mature when it can reliably answer:

> What changed?

> Which delivery was affected?

> Which pipeline stages were involved?

> How long did each stage take?

> What is abnormal compared with historical behavior?

> Which stage is the bottleneck?

> What evidence supports that conclusion?

> Did the deployment correlate with runtime degradation?

> Which systems disagree?

> How complete is the available data?

> What should an engineer investigate?

AI may later help explain these findings, but the underlying facts and measurements must remain deterministic.
