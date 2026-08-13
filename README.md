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

## DORA Metrics

DevPulse currently computes four core DORA-style delivery metrics:

| Metric | Description |
|---|---|
| 🚀 Deployment Frequency | Successful workflow executions per week |
| ⏱️ Lead Time for Changes | Time from merged PR to subsequent successful workflow |
| ⚠️ Change Failure Rate | Failed workflow executions relative to total executions |
| 🔧 Mean Time to Recovery | Time from failed workflow to subsequent successful workflow |

Metrics can be calculated over configurable look-back windows.

---

# 🏗️ Architecture

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