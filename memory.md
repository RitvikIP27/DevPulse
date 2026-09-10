# DevPulse — Running Project Memory

> This file is the persistent handoff context for future coding-agent sessions.
> Update it after every significant milestone.

---

# 1. Project Identity

**Name:** DevPulse

**Category:** Engineering Intelligence / Software Delivery Observability

**Core thesis:**

> DevPulse reconstructs software delivery across engineering systems, measures delivery performance, identifies deterministic bottlenecks/anomalies/conflicts, and eventually uses AI to reason over structured evidence.

---

# 2. Current Development Philosophy

Current phase:

```text
NO AI
```

The priority is:

```text
Collection
→ Normalization
→ Correlation
→ Delivery Trace
→ Historical Analytics
→ Bottleneck Detection
→ Anomaly Detection
→ Conflict Detection
→ Runtime / Incident Correlation
→ Evidence
```

AI comes afterward.

---

# 3. Existing MVP

The current MVP includes:

- GitHub ingestion
- Pull request ingestion
- GitHub Actions workflow ingestion
- PostgreSQL
- FastAPI
- React
- Docker Compose
- DORA-style metrics
- repository synchronization

---

# 4. Current Architectural Direction

Target flow:

```text
External Systems
 ↓
Connectors
 ↓
Raw Data
 ↓
Normalization
 ↓
Normalized Events
 ↓
Correlation
 ↓
Delivery Trace
 ↓
Analytics
 ↓
Evidence
 ↓
Future AI
```

---

# 5. Current Integrations

Implemented/initial:

```text
GitHub
GitHub Actions
```

Planned:

```text
Kubernetes
ArgoCD
Prometheus
PagerDuty
Jenkins
GitLab CI
```

---

# 6. Current Important Limitation

Historically, workflow runs were used as deployment-like data in the MVP.

This must evolve.

Final architecture must distinguish:

```text
CI
Build
Deployment
Production Deployment
Runtime
Incident
```

Do not treat all successful workflow runs as production deployments.

---

# 7. Product Differentiator

The intended differentiator is not simply a DORA dashboard.

It is:

```text
Cross-system delivery reconstruction
+
deterministic bottleneck detection
+
historical comparison
+
runtime/deployment conflict detection
+
evidence-backed RCA
```

AI is a later enhancement.

---

# 8. Current Product Navigation Target

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

---

# 9. Synthetic Validation Target

Create:

```text
devpulse-demo-pipeline
```

with:

- FastAPI
- Docker
- GitHub Actions
- Kubernetes

Required scenarios:

- healthy
- slow review
- slow CI
- failed CI
- failed deployment
- rollback
- runtime regression
- deployment/runtime conflict
- missing telemetry

---

# 10. PR Strategy

Development is intentionally PR-driven.

Each major coherent feature should become a PR.

Suggested sequence:

```text
Product shell
Domain model
Normalized events
Correlation
Delivery traces
Real deployment model
Pipeline mapping
DORA V2
Historical analytics
Bottlenecks
Anomalies
Conflict detection
Kubernetes
ArgoCD
Runtime
Incidents
Synthetic validation
Ground-truth tests
Evidence engine
AI RCA later
```

This is a guideline, not a rigid requirement.

---

# 11. Agent Behavior

Every stage:

```text
Inspect
→ Plan
→ Implement
→ Test
→ Verify
→ Document
→ Commit
→ Push
→ PR
→ Stop
```

Do not silently jump multiple major stages.

---

# 12. Documentation Set

All nine live in the **repository root**, alongside `backend/` and `frontend/`,
as AGENTS.md section 3 requires:

```text
PRD.md
AGENTS.md
CLAUDE.md
Design.md
architecture.md
rules.md
testing.md
memory.md
Decision.md
```

> **Discrepancy resolved 2026-09-10.** These files were originally created one
> level above the repository root, which placed them outside the git repository
> entirely — they were untracked and unversioned, and `CLAUDE.md` sat where the
> agent handbook would not be committed alongside the code it governs. They were
> moved into the repository root and committed. Recorded here per AGENTS.md
> section 2, which requires documenting a doc/code discrepancy rather than
> silently correcting it.

Plus generated engineering records under `docs/`:

```text
docs/architecture-audit.md   Stage 0 audit (evidence-backed, 25 findings)
```

---

# 13. Last Completed Stage

Update this section after every milestone.

```text
Stage:   12 + 13 + 14 — Runtime, incidents, and cross-system conflict detection
Status:  COMPLETE
Date:    2026-09-10
Branch:  feat/stage-12-14-runtime-incidents-conflicts

Summary:
  THE DIFFERENTIATOR WORKS. DevPulse detects that a deployment reported SUCCESS
  while the application it shipped degraded — and refuses to call it a cause.

Implementation:
  + migration 0004: runtime_observations + incidents
  + connectors/prometheus.py (query_range, NaN = absence not zero)
  + connectors/pagerduty.py (incidents by configured service id)
  + services/conflicts.py — before/after comparison + conflict detection
  + services/providers.py — one place answering "can we read runtime/incidents"
  + GET /api/conflicts ; Health page is now real
  + app/demo_seed.py — PRD 5 synthetic scenarios in a MARKED demo repo

  ADR-023: strength vocabulary is CORRELATED / POTENTIALLY_RELATED only.
  There is NO "CAUSED". A test asserts "caused" never appears in evidence
  except inside an explicit unknown.

  False-positive guards: <3 samples/side = no verdict; <50% worsening = noise;
  improvements are never degradations (direction is per-metric); incidents >60m
  after a deploy are not associated.

VERIFIED on the seeded scenarios:
  degraded deploy: error_rate 0.8 -> 18.4 (+2200%), latency 180 -> 910 (+405.6%)
                   status SUCCESS + CONFLICT(CORRELATED) + 1 incident
  healthy deploy:  0.8 -> 0.8, NO conflict (no false positive)
  with no providers: "cannot determine whether production stayed healthy"

Tests:   backend 111 passed, 0 xfailed; frontend 24 passed

PR:      #10

Next:    Stage 10 anomaly engine, or Stage 15/16 evidence package + AI RCA.
         AI is now unblocked: deterministic evidence (traces, baselines,
         bottlenecks, conflicts, coverage) all exist for it to reason over.
```

---

# 13a. Verified Facts About the Running System

These were established by execution on 2026-09-10. Trust them over assumption,
but re-verify before relying on them after significant change.

```text
Repo root:        /home/ritvik-kant/DevPulse/DevPulse  (nested one level)
Remote:           https://github.com/RitvikIP27/DevPulse.git
Branches:         main — CONTAINS THE MVP. It was merged via PR #1 on 2026-08-13.
                  An earlier note here claimed main held only LICENSE + README
                  and that the MVP was unmerged; that was read off a STALE local
                  main that had never been fetched. Always `git fetch` before
                  reasoning about branch topology.
                  feat/github-ingestion-dora (merged into main, PR #1)
                  docs/stage-0-architecture-audit (Stage 0 work)
                  chore/stage-0-5-foundation (Stage 0.5 work)
gh CLI:           installed but NOT authenticated; no credential helper; no GH_TOKEN
                  => cannot push or open PRs without the user acting first

Stack:            builds and runs. 3/3 containers healthy.
Schema owner:     Alembic. NEVER add create_all back (ADR-015). To change a
                  model you MUST add a migration or CI fails on drift.
Run tests:        backend  — cd backend && ./.venv/bin/python -m pytest
                             (venv is gitignored; recreate with python3 -m venv
                             .venv && .venv/bin/pip install -r requirements-dev.txt)
                  frontend — cd frontend && npm test
Demo note:        ingested data spans 2026-05-29..2026-07-19, so the default
                  30-day window shows "—". Select 90 days to see real numbers.
Routes:           GET /health, GET /api/metrics/dora, GET /api/repositories,
                  POST /api/ingest/sync (202), GET /api/ingest/jobs,
                  GET /api/deliveries, GET /api/deliveries/{id}
Tables (only 3):  repositories, pull_requests, workflow_runs
Host port clash:  RESOLVED — compose now publishes 55432. Connect from the host
                  with: psql -h localhost -p 55432 -U devpulse -d devpulse
Secret hygiene:   CLEAN. backend/.env is gitignored, untracked, never in history.

Test fixture:     the Docker volume devpulse_devpulse_pgdata still holds the
                  21 PRs / 90 workflow runs ingested during the audit.
                  Deliberately kept as a realistic fixture.
```

---

# 13b. Quantified Audit Findings (do not re-derive these)

```text
"Deployments" are not deployments:
  34 runs counted as deployments in 90d. Breakdown:
    Production CI Workflow     14   (CI)
    infra.yml                   8   (infrastructure)
    CD Workflow                 6   (plausibly a real deploy)
    Infrastructure Workflow     5   (infrastructure)
    CI Workflow                 1   (CI)
  => at most 6/34 (18%) are deployment-shaped; frequency overstated ~5.7x

Lead time is structurally broken, not merely imprecise:
  Computed as PR merge -> next successful run. A merge push triggers CI within
  seconds, so the matched run is never the deployment. Measured per PR:
  0.1, 0.1, 0.0, 0.1, 0.1 minutes. It reports webhook latency and would return
  0.0 no matter how slow real delivery is.

Ingestion failures are invisible:
  POST /api/ingest/sync returns 200 {"status":"sync started"} BEFORE work runs.
  An injected invalid token raised HTTPStatusError 401 inside the BackgroundTask
  and reached no log, no DB row, and no user. There is no sync-status table.

Correlation has no join key:
  No table stores commit SHA, branch, event or environment. This blocks delivery
  traces, bottlenecks, conflict detection and the evidence layer. Highest-priority
  schema gap, and cheap to fix.

Missing data reads as healthy:
  A repo with zero runs reports change_failure_rate 0.0 and deployment_frequency
  0.0, and then sorts as the BEST service. The stale "DevPulse" repo row does
  exactly this in the live API response.

Docstring lies:
  dora_metrics.py:9 documents a workflow_name_filter in github_client.py that
  does not exist; the code explicitly stores every run.
```

---

# 14. Current Known Limitations

Keep this list current.

```text
- Deployment identification depends on a human declaring the deploy workflow
  unless the repository uses a real deployment provider (ADR-021).
- Rework rate is a lower bound: remediation not preceded by an observed
  deployment failure is invisible without incident data.
- Ingestion has no incremental cursor yet: every sync refetches the window and
  stops at a 10-page ceiling.
- Runtime and incident integrations do not exist.
- AI RCA is intentionally deferred (ADR-008, AGENTS.md 5).
- Pipeline discovery is initially configuration-driven (ADR-009).
```

Remove items as they are genuinely solved.

---

# 15. Important Principle

Do not optimize for architectural complexity.

Optimize for:

```text
correctness
data integrity
correlation
explainability
testability
```
