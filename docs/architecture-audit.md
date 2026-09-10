# Stage 0 — Repository Audit & Architecture Report

**Date:** 2026-09-10
**Commit audited:** `f789046` (`feat/github-ingestion-dora`)
**Auditor scope:** full repository, running system, database, and live GitHub ingestion.

This report is the Stage 0 deliverable. It records what DevPulse actually is today,
what was verified by execution rather than by reading code, and which specific
defects and gaps must be addressed to evolve toward an engineering-intelligence
platform. No product code was changed during this audit.

---

## 1. Method

The audit was performed against a running system, not by inspection alone.

| Step | Action | Result |
|---|---|---|
| 1 | Static read of all 20 source files | Complete |
| 2 | `docker compose up --build` | Both images build; 3/3 containers healthy |
| 3 | `GET /health` | `200 {"status":"ok"}` |
| 4 | `GET /api/metrics/dora` | `200`, valid response shape |
| 5 | `GET /openapi.json` | 3 routes exposed |
| 6 | Frontend served + `/api` proxy through nginx | `200` on both |
| 7 | `POST /api/ingest/sync` against a real GitHub repo | Ingested 21 PRs, 90 workflow runs |
| 8 | Direct SQL interrogation of the resulting data | See §3 |
| 9 | Ingestion failure injection (invalid token) | See Finding 4 |

A host port collision on `5432` (local Postgres already bound) was worked around with a
throwaway compose override; the committed compose file was not modified. This is itself
recorded as Finding 12.

---

## 2. What exists and works

The MVP is real, runs, and ingests live data. This is a genuine foundation and is
preserved.

**Backend** — FastAPI app (`backend/app`), 3 routes, SQLAlchemy 2.0 models,
Postgres persistence, GitHub REST client with PR + Actions ingestion, DORA
calculation service, Pydantic response schemas.

**Frontend** — React 18 + Vite + TypeScript, Recharts bar chart, service metrics
table with threshold-based bottleneck flagging, window selector, manual sync trigger.

**Infrastructure** — Dockerfiles for both tiers, Docker Compose stack with a Postgres
healthcheck and dependency ordering, nginx reverse proxy for `/api`, Kubernetes
manifests (Deployments, Services, Ingress, PVC, ConfigMap, Secret), GitHub Actions CI
with three jobs.

**Secret hygiene** — verified clean. `backend/.env` exists locally, is matched by
`.gitignore:9`, is not tracked, and has never appeared in git history.

---

## 3. Verified runtime evidence

A real sync against `RitvikIP27/KubernesDeployment` produced 21 PRs and 90 workflow
runs spanning 2026-05-29 → 2026-07-19. The API then reported:

```json
{
  "service": "KubernesDeployment",
  "deployment_frequency_per_week": 2.64,
  "lead_time_hours": 0.0,
  "change_failure_rate_pct": 21.3,
  "mttr_hours": 0.1,
  "total_deployments": 34,
  "total_failures": 10
}
```

**Every one of these four numbers is a measurement artifact.** The data proves it.

### 3.1 `total_deployments: 34` counts things that are not deployments

Breakdown of the 34 successful runs counted as "deployments" in the 90-day window:

| Workflow counted as a deployment | Count | Actually a production deployment? |
|---|---|---|
| `Ritvik's Production CI Workflow` | 14 | No — CI |
| `.github/workflows/infra.yml` | 8 | No — infrastructure |
| `Ritvik's CD Workflow` | 6 | Plausibly yes |
| `Ritvik's Infrastructure Workflow` | 5 | No — infrastructure |
| `Ritvik's CI Workflow` | 1 | No — CI |

At most **6 of 34 (18%)** are deployment-shaped. Deployment frequency is therefore
overstated by roughly **5.7×**.

### 3.2 `lead_time_hours: 0.0` is structurally impossible to be correct

Lead time is computed as *PR merge → next successful workflow run*. Because a merge
push triggers CI and infra workflows within seconds, the "next successful run" is
never the deployment:

| PR | Merged at | Workflow actually matched | Measured lead time |
|---|---|---|---|
| #29 | 2026-07-09 20:31:46 | Ritvik's Infrastructure Workflow | 0.1 min |
| #27 | 2026-07-09 07:40:29 | Ritvik's Infrastructure Workflow | 0.1 min |
| #26 | 2026-07-09 06:01:11 | `.github/workflows/infra.yml` | 0.0 min |
| #25 | 2026-07-08 19:44:17 | Ritvik's Production CI Workflow | 0.1 min |
| #24 | 2026-06-22 18:17:28 | Ritvik's Production CI Workflow | 0.1 min |

The metric converges to zero for every PR. It measures *webhook latency*, not delivery
lead time. It will report `0.0` regardless of how slow the team's real delivery is.

### 3.3 `mttr_hours: 0.1` has the same defect

Recovery is *failed run → next successful run*, where the next success is typically an
unrelated concurrent workflow. Six minutes is not a recovery time; it is the gap to a
different pipeline finishing.

### 3.4 `change_failure_rate_pct: 21.3` measures the wrong population

This is the failure rate of *all CI/infra/CD workflow runs*. It contains no notion of a
production change causing degradation and requiring remediation. A flaky lint job and a
rolled-back production release are weighted identically.

**Conclusion:** the current DORA engine is a workflow-run statistics engine wearing DORA
labels. The numbers are confidently wrong, which is worse than absent — they are
presented without caveat in the UI.

---

## 4. Architectural assessment against the target

Today all responsibilities are collapsed into two modules:

```text
github_client.py  ──►  Postgres  ──►  dora_metrics.py  ──►  API  ──►  React
(fetch + map +                        (deployment semantics +
 persist + schema)                     metric math + ranking)
```

The target separates them:

```text
CONNECTORS → RAW INGESTION → NORMALIZATION → CORRELATION
          → DELIVERY TRACE → ANALYTICS → EVIDENCE → AI
```

| Target layer | Present today | Assessment |
|---|---|---|
| Connector abstraction | No | `github_client.py` is the only path; provider-coupled |
| Raw ingestion record | No | API payloads discarded after mapping |
| Normalized event model | No | Vendor tables only (`pull_requests`, `workflow_runs`) |
| Correlation | No | **Blocked — no commit SHA stored anywhere** |
| Delivery trace | No | No entity represents a change's lifecycle |
| Deployment model | No | Workflow runs stand in for deployments |
| Analytics | Partial | Exists but operates on vendor rows, not traces |
| Historical baselines | No | Only current-window values computed |
| Bottleneck engine | No | Two hardcoded UI thresholds in `ServiceMetricsTable.tsx:9` |
| Anomaly detection | No | — |
| Conflict detection | No | — |
| Data coverage / confidence | No | **Missing data renders as `0.0` and `—`, not as "unavailable"** |
| Evidence layer | No | — |
| AI reasoning | No | — |

**Critical structural blocker:** `WorkflowRun` stores no `head_sha`, `head_branch`,
`event`, or `environment`, and `PullRequest` stores no `merge_commit_sha` or first-commit
timestamp. Correlation is the foundation of every downstream capability, and correlation
requires a join key. **The database currently contains no key on which any two systems
could be correlated.** This is the single highest-priority schema gap.

---

## 5. Findings register

Severity: **S1** blocks correctness of user-facing output · **S2** architectural blocker ·
**S3** operational/robustness · **S4** hygiene.

| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | S1 | Any workflow run is treated as a production deployment, inflating deployment frequency ~5.7× | §3.1 |
| 2 | S1 | Lead time structurally collapses to ~0 for every PR | §3.2 |
| 3 | S1 | MTTR and change failure rate measure unrelated workflow populations | §3.3, §3.4 |
| 4 | S1 | **Ingestion failures are silently swallowed.** `BackgroundTasks` returns `200 {"status":"sync started"}` before work begins; a 401 raises inside the task and reaches no log, no DB row, and no user. Verified by injecting an invalid token — `HTTPStatusError: 401 Unauthorized` vanished entirely. No `SyncJob`/status persistence exists | `routes_ingest.py:16`, live test |
| 5 | S1 | Absent data is indistinguishable from healthy data. A repo with zero ingested runs reports `change_failure_rate_pct: 0.0`, `deployment_frequency: 0.0` and is sorted as the *best* service. The stale `DevPulse` repo row does exactly this in the live response | §3, `dora_metrics.py:46` |
| 6 | S2 | No commit SHA, branch, event or environment on any table — correlation is impossible | §4 |
| 7 | S2 | `dora_metrics.py` imports GitHub-specific models directly; analytics is hard-coupled to one provider | `dora_metrics.py:17` |
| 8 | S2 | No normalized event model, no raw-payload retention, no historical snapshots — history cannot be reconstructed or re-derived after a logic fix | §4 |
| 9 | S3 | **Zero tests.** No test file, no `conftest.py`, `pytest` absent from `requirements.txt`. The CI job named `backend-test` only runs `python -c "from app.main import app"` — an import check mislabelled as a test | `.github/workflows/ci.yml:27` |
| 10 | S3 | `alembic==1.13.3` is a dependency but no migration tree exists; schema is created by `Base.metadata.create_all` at startup. Any model change from here risks silent drift or data loss | `main.py:24` |
| 11 | S3 | Ingestion is capped at 3 pages × 50 items with no incremental cursor, no `since` parameter, no rate-limit handling, no retry, and no 429/5xx backoff. Every sync refetches the same window and silently truncates beyond 150 items | `github_client.py:64,126` |
| 12 | S3 | Compose publishes `5432` to the host, colliding with any local Postgres — the documented quickstart fails on such a machine | verified at §1 |
| 13 | S3 | `started_at` is `nullable=False` but is populated from `_parse_dt(run.get("run_started_at"))`, which returns `None` when the field is absent → `IntegrityError` on an otherwise valid run | `github_client.py:163` |
| 14 | S3 | `_parse_dt` hard-codes `%Y-%m-%dT%H:%M:%SZ`, producing naive datetimes and throwing on any offset form (`+00:00`) or fractional seconds that GitHub may return | `github_client.py:35` |
| 15 | S3 | PR upsert is query-then-insert with no unique constraint on `(repository_id, github_pr_number)`; concurrent syncs can duplicate rows | `models/events.py:19` |
| 16 | S3 | `print()` is the only sync feedback and never reaches logs — `PYTHONUNBUFFERED` is unset in the backend image. No structured logging anywhere | `github_client.py:227` |
| 17 | S3 | Lead-time and MTTR inner loops rescan the full success list per item (O(n²)); `compute_all_metrics` issues 2 queries per repo | `dora_metrics.py:51,66` |
| 18 | S4 | Module docstring claims runs are filtered to names containing `"deploy"` via a `workflow_name_filter` in `github_client.py`. **No such filter exists** — the code explicitly stores every run. Documentation contradicts behaviour | `dora_metrics.py:9-10` |
| 19 | S4 | `README.md` has one unclosed code fence and the file ends mid-diagram with no trailing newline — everything after the architecture block renders as code on GitHub | verified |
| 20 | S4 | README presents the four legacy DORA metrics; current DORA defines five (adds Deployment Rework Rate, reframes MTTR as Failed Deployment Recovery Time) | `README.md` |
| 21 | S4 | No repository CRUD. Repos come only from the `GITHUB_REPOS` env var; stale rows (e.g. `DevPulse`) cannot be removed and keep appearing as zero-valued services | §3 |
| 22 | S4 | `CORSMiddleware` allows all origins; no auth, authz, or rate limiting on any route | `main.py:12` |
| 23 | S4 | No `.dockerignore`; frontend `Dockerfile` copies only `package.json` and runs `npm install`, ignoring the committed lockfile — builds are non-reproducible | `frontend/Dockerfile:4` |
| 24 | S4 | `python-jose[cryptography]` declared but unused; `version:` key in compose is obsolete and emits a warning on every command; `@app.on_event("startup")` is deprecated in favour of lifespan handlers | multiple |
| 25 | S4 | The entire MVP (40 files, ~3.4k lines) sits unmerged on `feat/github-ingestion-dora`; `main` contains only `LICENSE` and `README.md` | `git ls-tree main` |

---

## 6. Technical debt that must be paid before Stage 2

Ordered by what unblocks the most downstream work:

1. **Alembic baseline** (Finding 10) — every subsequent stage adds tables. Without
   migrations, schema evolution is unsafe. This is the first thing to build.
2. **Test harness** (Finding 9) — correlation, baselines and scoring are logic-dense and
   cannot be validated by clicking. `pytest` + fixtures must precede the domain model.
3. **Commit SHA capture** (Finding 6) — cheap to add, and nothing in the target
   architecture works without it.
4. **Sync status persistence** (Finding 4) — required before any coverage or confidence
   claim can be honest.

---

## 7. Recommended stage sequencing

The roadmap's Stage 1 (product shell) is UI-facing and safe to do now; it does not
depend on the schema work. However, two corrections should be front-loaded because they
affect user trust immediately and are cheap:

- Label the current DORA output as **CI-proxy derived**, not production deployment
  derived, in both API and UI (addresses Findings 1–3, 5 honestly without a rewrite).
- Fix the README (Findings 19, 20) and the false docstring (Finding 18).

Proposed order: **Stage 0.5 (debt + honesty) → Stage 1 (product shell) → Stage 2
(domain model)**, with the Alembic baseline and pytest harness landing in Stage 0.5 so
Stage 2 has somewhere safe to land.

---

## 8. What this audit did not change

No product code, schema, dependency or configuration was modified. The only additions
are this document and the README corrections accompanying it. The Postgres volume
retains the 21 PRs / 90 workflow runs ingested during the audit; this is useful as a
realistic fixture and was deliberately kept.
