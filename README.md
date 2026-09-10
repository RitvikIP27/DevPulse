# ⚡ DevPulse

### Cloud-Native Engineering Intelligence & Delivery Analytics Platform

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions&logoColor=white)](https://github.com/RitvikIP27/DevPulse/actions)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Containerized](https://img.shields.io/badge/Containerized-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Cloud](https://img.shields.io/badge/Cloud-Ready-FF9900?logo=amazonaws&logoColor=white)](#roadmap)

> **DevPulse** is a cloud-native engineering intelligence platform that ingests GitHub engineering activity, computes DORA delivery metrics, and identifies potential delivery bottlenecks across repositories.

Built as a **college minor project**, DevPulse is being developed from a working data-ingestion MVP toward a broader engineering intelligence platform covering delivery analytics, bottleneck detection, engineering health, and actionable recommendations.

---

## 🧭 Current Status

### MVP — Working

- ✅ GitHub REST API integration
- ✅ Repository synchronization
- ✅ Pull request ingestion
- ✅ GitHub Actions workflow ingestion
- ✅ PostgreSQL persistence
- ✅ DORA metrics engine
- ✅ FastAPI REST API
- ✅ React dashboard
- ✅ Docker Compose local development stack
- ✅ Frontend → FastAPI API proxy
- ✅ Per-repository DORA metric calculation
- ✅ CI workflow for project validation

### 🚧 In Development

- ⏳ Multi-page dashboard
- ⏳ Repository management UI
- ⏳ Historical metric trends
- ⏳ Bottleneck detection
- ⏳ Engineering health scoring
- ⏳ Detailed repository analytics
- ⏳ Recommendations and remediation guidance
- ⏳ Authentication
- ⏳ GitHub webhooks / real-time ingestion

---

## 📋 Engineering Audit

A full Stage 0 audit of the running system — verified by executing the stack and
ingesting live GitHub data, not by code reading alone — is published at
[`docs/architecture-audit.md`](docs/architecture-audit.md).

It records what works, quantifies the defects in the current metrics with evidence,
and registers 25 findings by severity. Read it before making architectural changes.

**Headline finding:** the four metrics above are computed from CI workflow runs standing
in for deployments. On the audited repository only 6 of 34 counted "deployments" were
deployment-shaped, and measured lead time collapsed to ~0.1 minutes for every pull
request. The MVP ingestion, persistence, API and dashboard are sound; the delivery
*semantics* are what need to evolve.

### Target architecture

DevPulse is evolving from `GitHub → DORA dashboard` toward a layered delivery
intelligence system, where a deterministic pipeline establishes facts and AI reasons
only over structured evidence:

```text
CONNECTORS → NORMALIZED EVENTS → CORRELATION → DELIVERY TRACES
     → DORA / BOTTLENECKS / ANOMALIES → HISTORICAL BASELINES
     → EVIDENCE → AI REASONING → RCA + RECOMMENDATIONS
```

The guiding constraint: **connectors collect facts, normalization unifies them,
correlation reconstructs deliveries, analytics measures, and AI interprets.** Those
responsibilities are never collapsed, and AI is never the source of truth.

---

# 🎯 Problem

Modern engineering teams generate large amounts of delivery data across:

- Pull requests
- Code changes
- CI/CD pipelines
- Deployments
- Failures
- Recovery events

Raw activity does not automatically explain **where delivery is slowing down**.

DevPulse aims to turn this engineering activity into a single intelligence layer that answers:

> **Where is our delivery pipeline slowing down, why is it happening, and what should we improve?**

---

# 🧠 Core Capabilities

## Delivery Metrics (MVP — CI-proxy derived)

DevPulse currently computes four DORA-style delivery indicators. **These are derived
from GitHub Actions workflow runs used as a proxy for deployments, not from real
production deployment data.** They are directionally useful for comparing repositories
but are not yet valid DORA measurements.

| Indicator | How it is computed today | Known limitation |
|---|---|---|
| 🚀 Deployment Frequency | Successful workflow runs per week | Counts CI and infrastructure runs as deployments |
| ⏱️ Lead Time for Changes | PR merge → next successful workflow run | Collapses toward zero, because CI triggers seconds after merge |
| ⚠️ Change Failure Rate | Failed runs ÷ total runs | Measures all workflow failures, not production change failures |
| 🔧 Mean Time to Recovery | Failed run → next successful run | The next success is often an unrelated concurrent workflow |

Metrics can be calculated over configurable look-back windows.

> **Measurement caveat.** Until DevPulse ingests real deployment events, these numbers
> should be read as CI pipeline statistics. The quantified impact of each limitation is
> documented with evidence in [`docs/architecture-audit.md`](docs/architecture-audit.md).
> Replacing this proxy with an explicit deployment model — and reporting
> *"deployment data unavailable"* instead of a misleading number — is tracked as Stage 5
> of the roadmap.

Current DORA defines **five** metrics; DevPulse implements four of the legacy set today.
Deployment Rework Rate, and the reframing of MTTR as Failed Deployment Recovery Time,
arrive with the Stage 7 metrics engine.

---

# 🏗️ Architecture (current state)

```text
                       ┌──────────────────────┐
                       │       GitHub         │
                       │                      │
                       │ PRs + Actions Runs   │
                       └──────────┬───────────┘
                                  │
                                  │ REST API
                                  ▼
                       ┌──────────────────────┐
                       │   FastAPI Backend    │
                       │                      │
                       │ GitHub Ingestion     │
                       │ REST API             │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │     PostgreSQL       │
                       │                      │
                       │ Repositories         │
                       │ Pull Requests        │
                       │ Workflow Runs        │
                       └──────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │   DORA Engine        │
                       │                      │
                       │ Frequency            │
                       │ Lead Time            │
                       │ Failure Rate         │
                       │ MTTR                 │
                       └──────────┬───────────┘
                                  │
                                  │ REST API
                                  ▼
                       ┌──────────────────────┐
                       │    React Dashboard   │
                       │                      │
                       │ Metrics + Analytics  │
                       └──────────────────────┘
```
