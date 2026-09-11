# ⚡ DevPulse

### Engineering Intelligence & Software Delivery Observability

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions&logoColor=white)](https://github.com/RitvikIP27/DevPulse/actions)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React_+_TypeScript-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-66_backend_%2F_23_frontend-4ade80)](#testing)

> DevPulse reconstructs the lifecycle of a software change across engineering
> systems, measures delivery performance, and reports **exactly how much of the
> story it can actually see.**

---

## The idea

Every tool knows one fragment of a delivery. GitHub knows the pull request. CI
knows the build. A deployment platform knows the release. Monitoring knows
whether production stayed healthy afterwards. Nothing joins them.

DevPulse joins them on **commit identity**, and is explicit about what it cannot
observe:

```text
Connectors → Normalization → Correlation → Delivery Traces
          → Metrics / Baselines / Bottlenecks
          → Evidence → (later) AI reasoning
```

The deterministic layer establishes the facts. AI is deferred until there is
trustworthy evidence for it to reason over — see [ADR-008](Decision.md).

---

## What actually works today

| Capability | Status |
|---|---|
| GitHub + Actions ingestion, with pagination, retries and rate-limit handling | ✅ |
| Sync outcomes persisted and classified (`SUCCESS` / `PARTIAL` / `FAILED`) | ✅ |
| Commit-SHA correlation keys on every record | ✅ |
| **Delivery traces** — a change reconstructed across 10 pipeline stages | ✅ |
| Per-stage **data coverage** and analysis confidence | ✅ |
| DORA-style indicators | ⚠️ CI-proxy derived — see below |
| Nine-page dashboard, dark design system, responsive | ✅ |
| Bottleneck engine, health scoring, RCA | ⛔ Not built — pages say so |

### The delivery trace

The core object. A merged pull request is correlated to every workflow run
reporting the same merge commit:

```text
Delivery · PR #27                                          commit 13be8d5bc3

  SOURCE      ● Success        Commit 13be8d5bc3 on main
  REVIEW      ● Success        Open for review                          5m
  CI          ● Failed         10 workflow runs reported this commit  12.9h
  QUALITY     ○ Not observed   No code-quality integration connected
  BUILD       ○ Not observed   Build events not distinguished from CI
  ARTIFACT    ○ Not observed   No artifact registry connected
  DEPLOYMENT  ○ Not observed   No deployment provider connected
  ROLLOUT     ○ Not observed   No orchestrator connected
  RUNTIME     ○ Not observed   No monitoring provider connected
  INCIDENT    ○ Not observed   No incident provider connected

  3 of 10 stages observed
```

**Correlation is on commit identity, never on timing.** A run firing seconds
after a merge but carrying a different commit is left unlinked. `NOT_OBSERVED`
is a distinct status from `FAILED` — a delivery is not failed merely because
runtime telemetry is missing.

---

## Honesty about the metrics

This is the part most delivery dashboards get wrong, so DevPulse states it
plainly in the product, not just the docs.

No deployment provider is connected yet, so the current DORA-style numbers are
derived from **CI workflow runs standing in for deployments.** A [Stage 0
audit](docs/architecture-audit.md) measured the damage on a real repository:

- Only **6 of 34** counted "deployments" were deployment-shaped — frequency
  overstated roughly **5.7×**
- Lead time collapsed to **~0.1 minutes for every pull request**, because the
  matched run was the CI job the merge itself triggered

Both defects are locked in `xfail(strict=True)` tests that will **fail the build
the moment they are fixed**, forcing the marker to be removed
([ADR-016](Decision.md)).

Three display states are kept strictly apart throughout the UI:

```text
empty          the query ran and found nothing
unavailable    the metric cannot be computed from the data present
not observed   no integration reports this at all
```

A window with no completed runs renders `—`, never `0.0%`. A zero failure rate
reads as a healthy service, and in the audit an empty repository sorted as the
best performer.

---

## Quickstart

```bash
git clone https://github.com/RitvikIP27/DevPulse.git
cd DevPulse
cp backend/.env.example backend/.env    # add GITHUB_TOKEN and GITHUB_REPOS
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Postgres | `localhost:55432` |

Then open **Repositories → Sync from GitHub**, and watch the sync result appear
in the *Last sync* column.

> The database is published on `55432`, not `5432`, because developer machines
> very often already run a local Postgres — which made the old quickstart fail
> outright.

### Configuration

```bash
GITHUB_TOKEN=<a personal access token with repo scope>
GITHUB_REPOS=owner/repo,owner/another-repo
DATABASE_URL=postgresql://devpulse:devpulse@db:5432/devpulse
```

Secrets are read from the environment and never rendered in the UI.

---

## API

```text
GET  /health
GET  /api/repositories              tracked repos + per-stage data coverage
GET  /api/deliveries                delivery traces
GET  /api/deliveries/{id}           one trace, with correlation evidence
GET  /api/metrics/dora              delivery indicators (CI-proxy derived)
POST /api/ingest/sync               202 Accepted — runs in the background
GET  /api/ingest/jobs               what each sync actually did
```

---

## Testing

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest          # 66 passed, 3 xfailed

cd frontend && npm ci && npm test   # 23 passed
```

CI runs both suites, applies and reverses migrations against real PostgreSQL,
and **fails the build if a model has drifted from its migration.**

Connector tests use `respx` and touch no network.

---

## Architecture

```text
backend/
├── alembic/            migrations — the single owner of schema (ADR-015)
├── app/
│   ├── api/            thin routes
│   ├── core/           config, database, logging
│   ├── models/         SQLAlchemy entities
│   ├── schemas/        Pydantic API contracts
│   └── services/       ingestion, correlation, delivery traces, metrics
└── tests/

frontend/src/
├── components/         layout shell + reusable UI
├── pages/              nine pages
├── state/              filter context, async state
└── api/                single typed API client
```

Schema is owned by Alembic and applied by the container entrypoint before the
server starts. `create_all` is never used.

---

## Documentation

**New to the project? Start with
[`docs/explain/`](docs/explain/README.md)** — a fourteen-chapter walkthrough that
assumes no web development knowledge and covers every file and concept in the
codebase.

| Document | Purpose |
|---|---|
| [docs/explain/](docs/explain/README.md) | **Learn the whole project from scratch** |
| [PRD.md](PRD.md) | Product requirements and roadmap |
| [architecture.md](architecture.md) | Technical architecture |
| [Decision.md](Decision.md) | Architecture decision records (ADR-001 → 020) |
| [Design.md](Design.md) | Design system |
| [testing.md](testing.md) | Testing strategy |
| [rules.md](rules.md) | Engineering rules |
| [AGENTS.md](AGENTS.md) | Coding-agent handbook |
| [memory.md](memory.md) | Running project context |
| [docs/architecture-audit.md](docs/architecture-audit.md) | Stage 0 audit — 25 findings with evidence |

---

## Roadmap

Delivered: repository audit · migration and test foundation · product shell ·
correlation keys and sync observability · delivery traces.

Next: explicit deployment model (retiring the CI proxy) · historical baselines ·
deterministic bottleneck engine · anomaly detection · runtime and incident
connectors · cross-system conflict detection · evidence package · AI RCA.

---

## Licence

[MIT](LICENSE)
