# 06 · Backend tour, file by file

Every backend file, what it does, and why it exists.

## The shape of the backend

```text
backend/
├── alembic/              schema migrations (chapter 04)
├── tests/                the test suite (chapter 12)
├── entrypoint.sh         migrate, then start the server
├── requirements.txt      runtime dependencies
├── requirements-dev.txt  test-only dependencies
├── pytest.ini            test configuration
└── app/
    ├── main.py           assembles the application
    ├── core/             infrastructure: config, db, logging, security
    ├── models/           what is STORED (SQLAlchemy)
    ├── schemas/          what the API PROMISES (Pydantic)
    ├── api/              thin HTTP routes
    ├── services/         the actual logic
    └── connectors/       talking to outside systems
```

**The layering rule:** a route calls a service; a service calls models and other
services; a connector only fetches and maps. Routes contain no logic, and
services contain no HTTP. This is why `routes_bottlenecks.py` is 20 lines while
`services/bottlenecks.py` is 250.

---

## `app/main.py`

Assembles everything. Three jobs:

1. **Lifespan** — configure logging at startup. Notably *not* creating tables:
   that is Alembic's (ADR-015).
2. **CORS middleware** — which websites may call this API from a browser.
3. **Router registration** — and the security decision described in chapter 03:
   data routers are registered *with* `Depends(current_user)`, so a new route is
   protected by default.

---

## `app/core/` — infrastructure

| File | Purpose |
|---|---|
| `config.py` | All settings in one typed class, read from environment / `.env` |
| `database.py` | The engine, `SessionLocal`, `Base`, and the `get_db` dependency |
| `logging.py` | One stderr handler with a consistent format |
| `security.py` | bcrypt hashing, JWT issue/verify |
| `dependencies.py` | `current_user` — resolves and validates the caller |
| `webhook_security.py` | HMAC signature verification |

**`config.py`** is a Pydantic `BaseSettings` class. Every setting is typed and
documented, and secrets come from the environment — never the repository. Helper
properties turn comma-separated strings into lists (`repo_list`,
`cors_origin_list`).

**`logging.py`** exists because of a real failure. The MVP used bare `print()`,
and the Docker image did not set `PYTHONUNBUFFERED`, so sync output **never
appeared in `docker logs` at all**. Now everything logs through the standard
library and the image sets `PYTHONUNBUFFERED=1`.

**`security.py`** is covered in chapter 13. The short version: bcrypt is
*deliberately slow*, and a JWT is *signed, not encrypted*.

---

## `app/models/events.py`

Every table, in one file. Twelve classes, described in chapter 04's table.

The fields worth knowing by name:

- `PullRequest.merge_commit_sha` — the commit that actually landed on the base
  branch, and therefore the one a later deployment reports shipping. **This is
  the correlation key.**
- `WorkflowRun.head_sha` — the other side of the join.
- `Repository.last_synced_at` — the incremental sync cursor.
- `Deployment.provider` — `github_deployments` (authoritative) or
  `configured_workflow` (declared). Never mixed.
- `Anomaly.window_start` — part of a uniqueness key, truncated to the hour so
  repeated detection refreshes rather than duplicating.

---

## `app/api/` — routes

Twelve router files, all thin. `routes_bottlenecks.py` in full is in chapter 03.

| File | Endpoints |
|---|---|
| `routes_auth.py` | `/status` (public), `/register`, `/login`, `/me` |
| `routes_repositories.py` | Repositories + deployment-rule CRUD |
| `routes_ingest.py` | `POST /sync` (202), `GET /jobs` |
| `routes_metrics.py` | `GET /dora` |
| `routes_deliveries.py` | Delivery list and one trace |
| `routes_bottlenecks.py` | Stage bottleneck analysis |
| `routes_anomalies.py` | Anomaly list, acknowledge |
| `routes_conflicts.py` | Cross-system conflict reports |
| `routes_health_score.py` | Composite health |
| `routes_analysis.py` | Candidates, evidence package, RCA |
| `routes_webhooks.py` | **Two routers** — public receiver, protected listing |

`routes_webhooks.py` is the one exception to the "everything protected" rule,
and it is explicit about it: GitHub cannot present a bearer token, so the HMAC
signature *is* its authentication. Splitting the public receiver into its own
router keeps that exception visible instead of leaving a public hole inside a
router someone later assumes is protected.

---

## `app/services/` — the logic

This is where DevPulse actually lives. Chapter 07 covers the algorithms; here is
what each file is *for*.

### Ingestion and plumbing

| File | Responsibility |
|---|---|
| `github_client.py` | Fetch PRs and workflow runs; pagination, retries, rate limits, incremental cursor, `SyncJob` recording |
| `timestamps.py` | Parse every external timestamp into naive UTC, in one place |
| `errors.py` | Classify provider failures into a taxonomy |
| `sync_jobs.py` | Read back what each sync did |
| `webhooks.py` | Record a delivery, then process it |
| `providers.py` | One answer to "can we read runtime / incidents?" |

**`timestamps.py`** exists because the MVP used
`strptime(value, "%Y-%m-%dT%H:%M:%SZ")`, which produced naive datetimes and
**crashed outright** on any offset form like `+02:00`. One helper now owns the
conversion, and an unparseable value returns `None` rather than aborting a whole
sync.

**`errors.py`** distinguishes failures that mean different things. The subtle
case: GitHub returns `403` both for genuine permission problems *and* for
exhausted rate limits. The `x-ratelimit-remaining` header separates them.
Misclassifying sends someone to regenerate a perfectly good token instead of
simply waiting.

### The analytical engines

| File | Answers |
|---|---|
| `repositories.py` | "What can DevPulse see for this repository?" (coverage, confidence) |
| `deployments.py` | "Which records are real production deployments?" |
| `deliveries.py` | "What journey did this change take?" (correlation) |
| `dora_metrics.py` | "How fast and how reliably do we ship?" |
| `baselines.py` | "What is normal for this metric?" (median, p90, MAD) |
| `bottlenecks.py` | "Where is delivery time going?" |
| `anomalies.py` | "What changed recently?" |
| `conflicts.py` | "Do our systems disagree about what happened?" |
| `health.py` | "Overall, how healthy is this service?" |
| `evidence.py` | "What facts should AI be allowed to see?" |

`baselines.py` is the one to notice. Both `bottlenecks.py` and `anomalies.py`
import from it rather than computing their own medians. That is why the same
CI regression reports **+253.8% on both pages** — one definition of "median",
"baseline" and "regression" for the whole product.

### `app/services/ai/`

| File | Purpose |
|---|---|
| `provider.py` | The `AIProvider` Protocol — the vendor-neutral interface |
| `anthropic_provider.py` | The only implementation today |
| `prompts.py` | Versioned system prompt and prompt builder |
| `rca.py` | Orchestration: cache, call, integrity-check, persist |

A **Protocol** is Python's way of saying "anything with these methods will do".
Nothing above this layer imports the Anthropic SDK, so swapping providers means
adding one file.

The SDK is imported **inside the method**, not at module top. A module-level
import would take the entire API down if the optional dependency were missing —
letting an optional feature break the deterministic core, which is exactly what
ADR-008 exists to prevent.

---

## `app/connectors/`

| File | Talks to |
|---|---|
| `prometheus.py` | Prometheus `query_range` for runtime metrics |
| `pagerduty.py` | PagerDuty incidents |

Both are optional. Unconfigured, they report `NOT_CONFIGURED` — DevPulse never
substitutes a default endpoint, because silently querying the wrong system is
worse than saying "I cannot see this".

One detail in `prometheus.py`: Prometheus returns `NaN` for windows with no
data. DevPulse skips those samples, because **NaN is an absence of data, not a
measurement of zero**. Treating it as zero would invent a healthy reading.

---

## `app/demo_seed.py`

Creates a clearly marked demo repository with the scenarios from the PRD, so
conflict detection can be demonstrated without a real Prometheus.

Every record carries a `demo` provider, the repository is named
`devpulse-demo/payments-api`, and the whole thing is gated behind `DEMO_MODE`.
Demo data is **never** written into a real repository. `--clear` removes it.

---

## Reading order for the code itself

If you want to read the source rather than these docs, this order builds up
naturally:

```text
1. models/events.py        what exists
2. services/timestamps.py  the smallest real file
3. services/baselines.py   pure statistics, no database
4. services/deliveries.py  correlation — the heart of the product
5. services/bottlenecks.py how a score is built and explained
6. services/conflicts.py   the differentiating feature
7. services/evidence.py    the AI boundary
8. main.py                 how it is all wired together
```

---

**Next:** [07 · The analytical engines](07-analytical-engines.md)
