# DevPulse — Architecture Decision Record

This document records important decisions made during development.

Do not record every trivial implementation detail.

Record decisions that materially affect architecture, technology, data model, product behavior or future extensibility.

---

# ADR-001 — PostgreSQL over MongoDB

**Status:** Accepted

## Context

DevPulse stores strongly related entities:

```text
Repository
Service
Pipeline
Delivery
PR
Commit
CI
Deployment
Runtime
Incident
```

The system requires:

- relationships
- filtering
- historical queries
- aggregations
- consistency
- transactional ingestion

## Decision

Use PostgreSQL as the primary datastore.

## Why

The domain is relational.

Delivery correlation requires relationships across entities.

DORA and historical analytics require SQL aggregation.

PostgreSQL also supports JSON fields where provider-specific metadata needs flexible storage.

## Rejected Alternative

MongoDB would provide flexible documents, but the core domain is relationship-heavy and analytical queries would become unnecessarily application-driven.

---

# ADR-002 — FastAPI for Backend

**Status:** Accepted

## Context

DevPulse needs:

- REST APIs
- typed schemas
- Python analytics
- integration with GitHub
- statistical processing

## Decision

Use FastAPI.

## Why

It provides:

- strong Python typing
- Pydantic integration
- automatic API documentation
- straightforward async/background capabilities
- natural fit with Python analytics

---

# ADR-003 — React + TypeScript for Frontend

**Status:** Accepted

## Context

DevPulse requires a dashboard with:

- charts
- delivery timelines
- filtering
- multiple pages
- reusable components

## Decision

Use React with TypeScript.

## Why

React provides mature component architecture and TypeScript improves correctness for API-driven UI.

---

# ADR-004 — Docker Compose for Initial Local Platform

**Status:** Accepted

## Context

Development requires:

```text
frontend
backend
PostgreSQL
```

## Decision

Use Docker Compose initially.

## Why

It provides simple reproducible local infrastructure without premature orchestration complexity.

Kubernetes remains a deployment target and integration domain, not a requirement for local development.

---

# ADR-005 — Provider Adapter Architecture

**Status:** Accepted

## Context

DevPulse must eventually support many engineering tools.

## Decision

Use provider-specific connectors/adapters that normalize into a common DevPulse event model.

## Why

Analytics must remain provider-independent.

This allows GitHub Actions and Jenkins to produce equivalent CI semantics.

---

# ADR-006 — Normalized Event Model

**Status:** Accepted

## Context

Vendor APIs expose incompatible schemas.

## Decision

Introduce normalized DevPulse delivery events.

## Why

Correlation and analytics should operate on domain semantics rather than vendor JSON.

---

# ADR-007 — Delivery Trace as Core Domain Object

**Status:** Accepted

## Context

DORA metrics and bottleneck analysis require connecting multiple events belonging to one change.

## Decision

Treat a Delivery Trace as a first-class object.

## Why

It provides the bridge between:

```text
source
→ CI
→ build
→ deployment
→ runtime
→ incident
```

and allows the platform to reason about the complete lifecycle.

---

# ADR-008 — Deterministic Analytics Before AI

**Status:** Accepted

## Context

The product eventually needs AI RCA, but AI without trustworthy structured evidence would produce unreliable conclusions.

## Decision

Build all foundational analysis deterministically before introducing AI.

## Why

This creates:

- reproducibility
- testability
- explainability
- trustworthy evidence
- lower AI hallucination risk

AI becomes a reasoning layer rather than a source-of-truth layer.

---

# ADR-009 — Explicit Pipeline Mapping Before Automatic Discovery

**Status:** Accepted

## Context

Automatic discovery is attractive but complex.

## Decision

Start with explicit integration-to-stage mapping.

## Why

It is easier to validate and provides a clear configuration model.

Automatic discovery can be layered on later.

---

# ADR-010 — Do Not Treat Every CI Run as a Production Deployment

**Status:** Accepted

## Context

The MVP used workflow runs as deployment-like events.

## Decision

Introduce explicit deployment modeling.

## Why

CI success does not imply production deployment.

Production DORA metrics require production delivery semantics.

---

# ADR-011 — Evidence Before Causality

**Status:** Accepted

## Context

A runtime incident may occur after a deployment without necessarily being caused by it.

## Decision

Represent temporal relationships and correlations separately from causal claims.

## Why

Temporal proximity is evidence, not proof.

DevPulse should communicate:

```text
observed after
correlated with
likely contributor
```

when causality is not established.

---

# ADR-012 — Data Coverage as a Product Feature

**Status:** Accepted

## Context

A platform integrating many systems will often have incomplete telemetry.

## Decision

Expose data coverage and analysis confidence.

## Why

Users must know what DevPulse can and cannot conclude.

---

# ADR-013 — Avoid Premature Distributed Infrastructure

**Status:** Accepted

## Context

DevPulse may eventually need workers and queues.

## Decision

Start with:

```text
React
FastAPI
PostgreSQL
Docker Compose
```

Add distributed infrastructure only when scale or reliability requirements justify it.

---

# ADR-014 — PR-Driven Development

**Status:** Accepted

## Context

The project is being developed incrementally and must demonstrate continuous engineering progress.

## Decision

Every meaningful milestone should be represented by a coherent PR.

## Why

This creates:

- reviewable changes
- visible progress
- safer iteration
- cleaner Git history
- easier rollback

---

# ADR-015 — Alembic Owns the Schema; No create_all at Startup

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 0.5

## Context

The MVP created its schema with `Base.metadata.create_all` in a FastAPI startup
hook, while `alembic` sat in `requirements.txt` unused with no migration tree.

`create_all` only ever creates missing tables. It never alters an existing one.
Every stage from here adds or changes columns and tables — normalized events,
deliveries, deployments, sync jobs — so under `create_all` a model change would
apply silently on a fresh database and not at all on an existing one, leaving
environments quietly divergent.

## Decision

Alembic is the single owner of schema. `create_all` is removed from application
startup. Migrations are applied by the container entrypoint before uvicorn
starts, and the entrypoint fails fast so a container cannot come up healthy
against a schema it does not match.

Revision `0001_baseline` snapshots the MVP schema exactly. It creates each table
only when absent, because development and demo databases already contain those
tables from the `create_all` era — including the volume holding the Stage 0 audit
fixture. That guard is specific to the baseline; later migrations describe real
deltas and must not copy the pattern.

## Why

Satisfies rules.md 13. Makes schema evolution reviewable in the diff, reversible,
and identical across environments.

CI enforces this: it applies migrations to an empty database, downgrades to base,
then runs `alembic revision --autogenerate` and fails if any operation is
produced. A model changed without a migration cannot merge.

## Rejected Alternative

Asking existing environments to run `alembic stamp head` by hand. It cannot be
automated in the entrypoint and silently diverges for anyone who forgets.

---

# ADR-016 — Known Defects Are Locked in Executable Tests

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 0.5

## Context

The Stage 0 audit proved several defects with live data: CI runs counted as
deployments, lead time collapsing to zero, and absent data reporting as `0.0`
and ranking as the healthiest service.

These defects are fixed by later stages. Recording them only in prose risks them
being forgotten, half-fixed, or — worse — fixed without anyone noticing, leaving
the documentation permanently wrong.

## Decision

Each proven defect gets a test asserting the behaviour the product *requires*,
marked `xfail(strict=True)` with a reason naming the fixing stage.

## Why

The defect becomes executable rather than narrative. The suite stays green while
the defect stands, and `strict=True` means that the moment the behaviour is
fixed the test fails loudly — forcing the marker to be removed and the fix to be
acknowledged. A defect cannot be silently fixed or silently reintroduced.

This is how PRD section 5's ground-truth expectations enter the codebase before
the engine capable of satisfying them exists.

---

# ADR-017 — Unbuilt Capabilities Render as Planned, Never as Empty or Zero

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 1

## Context

The product shell introduces nine pages, but only three have an engine behind
them. Deliveries, Bottlenecks, Health and Analysis have no backing data at all.

The conventional move is to fill them with placeholder charts and sample
numbers so the product demos well.

## Decision

Pages without an engine render an explicit *planned* state naming the stage that
will build them and what must exist first. They show no numbers whatsoever.

Three display states are kept distinct throughout the UI:

```text
empty          the query ran and found nothing
unavailable    the metric cannot be computed from the data present
planned        DevPulse cannot answer this question yet
```

## Why

Placeholder data is indistinguishable from real data to anyone looking at the
screen, which is exactly the failure rules.md 11 and AGENTS.md 12 forbid. A
product whose entire thesis is *evidence before inference* cannot ship a
dashboard of invented numbers.

The same rule governs real metrics. A window containing no completed workflow
runs renders `—`, not `0.0%` — because a zero failure rate reads as a healthy
service, and the audit showed an empty repository sorting as the best performer.
The backend still returns `0.0` here; correcting that is Stage 6, and the UI
declines to repeat it in the meantime.

## Consequence

The interface openly advertises how much of the product is unbuilt, including a
`SOON` marker in the sidebar. That is the intended trade: an engineering
audience trusts a tool that states its limits far more than one that hides them.

---

# ADR-018 — Naive UTC Storage with Conversion at the Provider Boundary

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 2

## Context

The MVP parsed timestamps with `strptime(value, "%Y-%m-%dT%H:%M:%SZ")`, which
produced naive datetimes and raised outright on any offset form or fractional
seconds a provider is entitled to return. Metric code then compared those naive
values against `datetime.now(timezone.utc)`, mixing representations.

## Decision

Every external timestamp is parsed as timezone-aware, converted to UTC, and
stored naive. One helper, `services/timestamps.parse_utc`, owns the conversion,
and an unparseable value returns `None` rather than raising.

## Why

rules.md 4 requires a consistent database representation and forbids silently
mixing local time with UTC. Naive-UTC satisfies both, provided the conversion
happens in exactly one place — which is what makes it testable.

`TIMESTAMP WITH TIME ZONE` would be stricter, but SQLAlchemy returns naive
datetimes from SQLite regardless, so adopting it would force every
database-touching test onto PostgreSQL. That cost is not justified while all
timestamps originate from a single provider in UTC.

## Migration path

When a provider supplies genuine local-time semantics, move the columns to
`timestamptz` and move the DB-backed tests onto PostgreSQL. The single
conversion helper is the only code that changes.

## Consequence

A malformed timestamp skips one record with a warning rather than aborting a
sync. Records missing a NOT NULL timestamp are skipped outright — inventing one
would corrupt every duration derived from it.

---

# ADR-019 — Every Sync Records Its Outcome

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 2

## Context

`POST /api/ingest/sync` returned `200 {"status": "sync started"}` before doing
any work. The audit injected an invalid token and watched the resulting
`HTTPStatusError: 401` reach no log, no database row and no user.

## Decision

Ingestion writes a `SyncJob` row recording status, counts, and a classified
error. The endpoint returns **202 Accepted**, and `GET /api/ingest/jobs` reports
what actually happened.

Status distinguishes `PARTIAL` from `FAILED`: a sync that wrote some records
before failing leaves usable but incomplete data, and that difference decides
whether the metrics built on it can be trusted.

Errors are classified into the taxonomy from architecture.md 11 rather than
flattened. A 403 carrying `x-ratelimit-remaining: 0` is a `RATE_LIMIT`, not an
`AUTHORIZATION_ERROR` — misclassifying it sends someone to rotate a working
token instead of waiting for the quota to reset.

## Why

PRD 2.6 requires DevPulse to report data coverage honestly. Coverage cannot be
honest if the system does not know whether its own ingestion succeeded.

---

# ADR-020 — Delivery Traces Are Derived on Read, Not Persisted

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 3

## Context

A delivery trace links a merged pull request to every record reporting the same
commit. The obvious implementation is a `deliveries` table populated during
ingestion.

## Decision

Traces are computed on read from the records already stored.

## Why

The inputs are persisted and the computation is deterministic, so the trace adds
no information the database lacks. Deriving means a change to the correlation
rules takes effect immediately, rather than requiring a backfill of every
historical trace — which matters while those rules are still being developed.

## When this changes

Persist traces once correlation spans providers that arrive out of order, or
once trace assembly becomes too expensive to run per request. Neither is true
with one provider and a commit-keyed lookup.

## Correlation constraint

Only exact commit-SHA matches link records. Timestamp proximity is never used to
establish identity (rules.md 9). A merged pull request with no merge commit is
counted and reported as uncorrelatable rather than attached to whichever change
is nearest in time — which is precisely the mistake that made the MVP's lead
time collapse to zero.

Unobserved stages carry no verdict. A delivery is not FAILED because runtime
telemetry is missing (ADR-011); `NOT_OBSERVED` is a distinct status from
`FAILED`.

---

# ADR-021 — Deployments Come From a Provider or a Declared Rule, Never From CI

**Status:** Accepted · supersedes the MVP behaviour described in ADR-010
**Date:** 2026-09-10
**Stage:** 5

## Context

ADR-010 established that a successful CI run is not a production deployment. It
did not say where deployments should come from instead.

Most repositories have no deployment platform. The audited repository has no
GitHub Deployments and no configured environments — but it does have a workflow
named "CD Workflow" that performs deployment. Something has to bridge that gap
without guessing.

## Decision

Deployments are resolved from one of two sources, in order of authority:

1. **`github_deployments`** — the provider's own Deployments API. Authoritative:
   the platform is asserting that a commit reached an environment.
2. **`configured_workflow`** — a rule a human declared, naming which workflow
   deploys. Used only when no deployment provider exists (ADR-009: explicit
   configuration before automatic discovery).

The two are never mixed. If the provider supplied any deployment, rule-derived
rows are ignored, because blending an authoritative source with a declared one
produces a number no one can explain.

When neither yields anything, every deployment-derived metric reports `null`
with a reason. There is no fallback to counting CI runs.

## Why

Heuristics were the original defect. Matching workflow names containing "deploy"
would have recreated it in a subtler form: on the audited repository that
substring also matches infrastructure workflows.

## Measured effect

Configuring the real deployment workflow on the audited repository moved
deployment frequency from **2.64/week to 0.47/week — a 5.6x correction**, closely
matching the 5.7x overstatement the Stage 0 audit predicted. Change fail rate
moved from 21.3% to **53.8%**, because the CD workflow genuinely fails far more
often than the CI runs that were diluting it.

Lead time is now measured from a pull request merging to the deployment carrying
that same commit, matched by commit rather than by time order. This is what the
MVP got wrong: it took the next successful run after a merge, which was always
the CI job the merge itself triggered.

## Consequence

Removing a rule deletes the deployments derived from it. Those rows were an
interpretation of CI runs, and keeping them would leave metrics alive on a
mapping the user has withdrawn.

All three `xfail(strict=True)` defect locks from ADR-016 are now ordinary
passing tests, and their markers have been removed as that ADR requires.

---

# ADR-022 — Bottleneck Scoring Is Weighted, Renormalised and Decomposable

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 8/9

## Context

The obvious bottleneck rule is "the slowest stage wins". It is wrong. A stage
that has always taken twenty minutes is a cost, not a constraint. The stage that
used to take five minutes and now takes forty is where delivery is being lost,
even though it is not the slowest.

## Decision

Four independent signals, weighted:

```text
latency contribution   0.40   share of total measured delivery time
historical regression  0.25   change against the immediately preceding period
failure impact         0.20   share of observations of this stage that failed
frequency              0.15   share of deliveries passing through the stage
```

The score is the weighted sum, on 0-100. Every component is returned with its
value, weight, contribution and a sentence explaining it, and the UI renders the
breakdown alongside the score.

**Weights are renormalised over available signals.** When no baseline exists the
regression component is dropped and the remaining weights are rescaled to sum to
1.0. Scoring a missing baseline as zero would penalise a genuinely constrained
stage for the accident of having no history.

## Statistical choices

Median and median absolute deviation, not mean and standard deviation. Delivery
data is heavily skewed: on the audited repository CI has a median of 4.2 minutes
and a p90 of 609 minutes. A mean would describe neither.

The baseline is the equally long period immediately preceding the window, so
like is compared with like rather than against all of history.

## Refusals

The engine declines to conclude rather than guessing:

- Fewer than 3 deliveries in the window: no bottleneck is named, and the
  response says how many were found and why that is too few.
- Fewer than 5 baseline samples: the regression signal is reported as
  unavailable with the reason. "Not enough history" and "no regression" are
  different claims and must not be collapsed.
- A change below 25% is normal variation, not a regression.
- An improvement never contributes to a bottleneck score.

## Why decomposable

PRD constraint 9 requires every score to be explainable from its inputs. A
number no one can take apart is not evidence, and a bottleneck engine that
cannot justify itself will simply not be believed by the engineers it is
advising.

---

# ADR-023 — Conflicts Are Reported as Correlations, Never as Causes

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 12/13/14

## Context

A deployment platform reporting SUCCESS is describing its own control plane. It
knows the rollout mechanism completed; it knows nothing about whether the
application it shipped still works. When monitoring disagrees, reporting
"healthy" is worse than reporting nothing.

## Decision

DevPulse compares runtime metrics in a window before each deployment against the
same window after, and raises a conflict when the control plane and runtime
disagree. Every conflict carries three things: what each system reported, the
evidence, and an explicit list of what remains **undetermined**.

The strength vocabulary is deliberately closed:

```text
CORRELATED             the two were observed together
POTENTIALLY_RELATED    the two occurred near each other
```

There is no `CAUSED`. Temporal proximity is evidence, not proof (ADR-011,
rules.md 10), and omitting the vocabulary is the only reliable way to stop a
caller promoting a correlation into a causal claim. A test asserts the word
"caused" never appears in generated evidence except inside an *unknown*.

## Guards against false positives

- Fewer than 3 samples on either side yields no verdict.
- A relative worsening below 50% is noise.
- Improvements are never degradations; direction is interpreted per metric,
  since higher is worse for error rate but better for availability.
- An incident more than 60 minutes after a deployment is not associated with it.
- A deployment with nothing to report is omitted, so the page shows signal.

## Providers are optional and their absence is stated

Prometheus and PagerDuty are configured, never defaulted. Silently querying the
wrong endpoint is worse than reporting that runtime data is unavailable. With
neither connected, the response says plainly that DevPulse can confirm a
deployment reported success but cannot determine whether production stayed
healthy.

## Demonstrability

Because most repositories have no monitoring, the synthetic reference scenarios
from PRD 5 are seeded by `python -m app.demo_seed` into a clearly marked demo
repository, with every record carrying a `demo` provider. Demo data is never
written to a real repository, and `DEMO_MODE` gates whether it is readable.

---

# ADR-024 — AI Receives a Deterministic Evidence Package and Nothing Else

**Status:** Accepted
**Date:** 2026-09-10
**Stage:** 15/16

## Context

ADR-008 deferred AI until the deterministic pipeline could establish facts.
That pipeline now exists: delivery traces, baselines, bottleneck scoring,
runtime comparison, conflict detection and coverage.

## Decision

`services/evidence.py` assembles one `EvidencePackage` per deployment from those
engines. The AI layer receives that object serialised, and nothing else. It has
no database session, no provider credentials, no log access.

Three guards sit around it:

**Structured output.** The model must return the `RcaResult` schema, which
separates `observed_facts` from `inferences`, requires `alternative_hypotheses`
with their supporting and contradicting evidence, and requires `unknowns`. Prose
is where unsupported certainty hides; a schema makes the model commit to which
category each statement belongs in.

**Integrity checking.** Numeric claims in the summary, likely cause and observed
facts are checked against the evidence text. Anything unsupported is returned as
an `integrity_warning` and rendered next to the analysis. This cannot prove an
analysis sound, and is not meant to — it catches the specific failure that
matters most, a confident-looking figure the model produced rather than read.

**Caching by evidence hash.** An analysis is stored with the exact evidence,
model, and prompt version that produced it. Identical facts reuse the stored
result rather than being paid for again, and any analysis can be traced back to
its inputs.

## Internal consistency

The delivery trace is built from source control alone, so it marks DEPLOYMENT,
RUNTIME and INCIDENT unobserved regardless of what other providers reported. The
evidence builder reconciles those three stages against the deployment, runtime
comparison and incidents before assembly. Without that, a package could state
runtime was not observed while also carrying a runtime-degradation conflict, and
self-contradictory evidence is exactly what must never reach a model.

## Degradation

With no provider configured the evidence package is still built and returned,
with an explicit reason. The deterministic layer is the product; AI is an
interpretation of it, and its absence must not hide the facts.

The vendor SDK is imported lazily inside the provider. A module-level import
would take the whole API down if the optional dependency were missing — an
optional feature must never be able to break the deterministic core.

## Provider abstraction

`AIProvider` is a Protocol. `AnthropicProvider` is the only implementation
today; tests drive a fake. No test calls a real model: that would be slow, cost
money, and make the suite non-deterministic — and what is under test is
DevPulse's handling of model output, not the model.

---

# ADR-025 — Anomalies Are Persisted, Conservative, and One-Directional

**Status:** Accepted
**Date:** 2026-09-11
**Stage:** 10

## Context

Bottleneck scoring answers "where is delivery time going?". It does not answer
"what changed recently?" — a stage can be the largest cost without anything
having moved.

## Decision

A separate anomaly engine compares a short recent window against the three
periods preceding it, using the **same** `services/baselines.py` primitives the
bottleneck engine uses. One definition of median, baseline and regression for
the whole product, so the same number can never disagree between two pages.

Anomalies are **persisted**, not derived on read. A derived-only anomaly could
never answer "when did this start?", cannot be acknowledged, and vanishes the
moment the metric recovers — losing exactly the history that makes it useful.

## Conservatism is the design

A monitoring surface that cries wolf gets ignored, and an ignored surface is
worse than none: it costs attention and returns nothing. So:

- A change below 25% is normal variation, matching the bottleneck engine's
  threshold so the two agree.
- Fewer than 5 baseline samples means nothing is claimed, with the reason stated.
- **Improvements are never anomalies.** CI getting three times faster is good
  news; reporting it would train people to ignore the page.
- Severity is banded on magnitude: HIGH means roughly a tripling or worse, which
  is hard to dismiss as noise.

## Idempotence

Detection runs on every page load, so the uniqueness key is
`(repository, metric, window_start)` with `window_start` truncated to the hour.
An untruncated timestamp made every run a distinct window and inserted a
duplicate instead of refreshing — found by a test asserting that running
detection twice leaves one row.

## Verified

On the audited repository the engine reports CI duration moving from 3.25m to
11.5m (+253.8%, HIGH) — the same figure the bottleneck engine independently
reports, which is the intended consequence of sharing one statistics module.

---

# ADR-026 — Health Score Averages Only What It Can Measure

**Status:** Accepted
**Date:** 2026-09-11
**Stage:** 18

## Context

A composite score is the easiest number in the product to get wrong. Roll up
five dimensions naively and a team with no monitoring connected is punished for
DevPulse's blind spot; treat missing data as zero and an empty repository looks
broken rather than unknown.

## Decision

Five dimensions — DELIVERY, STABILITY, PIPELINE, RUNTIME, OBSERVABILITY — each
the mean of named, bounded inputs. Every input carries the measurement it came
from and a sentence stating how it became points, and the UI renders that
breakdown beneath the score.

- A dimension with no measurable input scores **null**, not zero, with a reason.
- The overall figure is the mean of **scorable dimensions only**.
- Thresholds are named constants, not inline numbers, so the rubric is visible
  and arguable (rules.md 3).
- Banding is linear between thresholds rather than a step, so a service just
  outside "good" does not look identical to one far outside it.

OBSERVABILITY deliberately scores **DevPulse's own visibility**, not the team's
performance, and its input says so. It is the one dimension that is always
measurable, which is why a bare repository still receives a low score rather
than no score — low because little is visible, which is the honest reading.

## Why decomposable

PRD constraint 9 requires it. The practical reason is that a composite nobody
can take apart gets argued with rather than acted on: an engineer shown "68" asks
"why?", and a page that cannot answer loses the argument.

## Verified

On real data: the repository with CI failing and regressing scores PIPELINE 4.5
while its DELIVERY is 59.4 — the composite does not hide a bad dimension behind
good ones. The demo service scores RUNTIME 50.0, exactly one of its two
deployments being conflict-free.

---

# ADR-027 — Authentication Is Opt-In, Enforced at the Router, and Fails Closed

**Status:** Accepted
**Date:** 2026-09-11
**Stage:** 23

## Context

Until now DevPulse had no authentication and `allow_origins=["*"]`. That is fine
on a laptop and unacceptable anywhere else — it was the last genuine production
blocker.

## Decision

**Opt-in via `AUTH_ENABLED`, default off.** A local single-user install should
not be forced through a login it does not need, and a tool that demands a
password before showing anything gets abandoned during evaluation. Turning it on
is one environment variable, and it must be on before exposing DevPulse beyond
localhost.

**Enforced at the router, not per handler.** Every data router is included with
`dependencies=[Depends(current_user)]`. Per-handler dependencies are how auth
holes appear: someone adds an endpoint and forgets the decorator. Declaring it
once means a new route is protected *by default* and would have to be
deliberately excluded. A test walks eight endpoints and asserts 401 on each.

**Fails closed.** A token that is expired, tampered with, signed by another key,
or belongs to a deleted or deactivated user is rejected identically. Checking the
signature alone would keep honouring a token for an account that no longer
exists, so the user is re-loaded and re-checked on every request.

## Password handling

bcrypt, with a per-hash random salt so two users sharing a password do not share
a digest. bcrypt is *deliberately slow*, and that slowness is the entire defence
— a fast hash like SHA-256 is the wrong tool precisely because it is fast.

Passwords over 72 bytes are **rejected rather than truncated**: bcrypt silently
ignores the excess, so accepting would quietly weaken a password the user
believes is long.

## Deliberate information hygiene

- Login returns one message for every failure. Distinguishing "no such account"
  from "wrong password" lets anyone enumerate which emails are registered.
- The JWT carries only `sub`, `exp`, `iat`. A JWT is **signed, not encrypted** —
  anyone can read it — so it must never carry a secret. A test asserts the claim
  set is exactly those three.
- Registration is open only while no account exists, so a fresh install can
  bootstrap its owner. An always-open endpoint that mints accounts would make
  authentication pointless.

## Email validation

`EmailStr` was removed. The library behind it rejects `admin@devpulse.local`
outright, because `.local` sits on a hard-coded special-use list with no flag to
bypass. DevPulse is self-hosted and routinely runs on internal domains, and
refusing a valid internal address at sign-up is a worse failure than accepting
one that happens to be undeliverable. Syntax is now checked directly, which also
removes a dependency (rules.md 16). Whether mail can be delivered is a
mail-server concern, not a sign-up concern.

## Verified live

Nine behaviours against the running stack: anonymous 401, public status,
bootstrap registration, authenticated 200, registration closing with 403, a
single message on bad credentials, successful login, `/health` staying public
for liveness probes, and a forged token rejected.

---

# ADR-028 — Webhooks Are a Signal; the REST API Stays the Source of Truth

**Status:** Accepted
**Date:** 2026-09-11
**Stage:** 22

## Context

Until now ingestion refetched the whole window on every sync, capped at ten
pages. That is affordable at three pages and not at a hundred, and it makes
frequent syncing wasteful — DevPulse re-reads thousands of unchanged records to
discover a handful of new ones.

## Decision

**Incremental sync.** Each repository carries `last_synced_at`. Pull requests
come back newest-updated first, so once a record older than the cursor appears,
everything after it is older still and fetching stops.

The cursor advances **only on a fully successful sync**. After a PARTIAL sync it
stays where it was — otherwise the records the failure skipped would never be
fetched, and the gap would be permanent and invisible.

**Webhooks are a signal, not a payload.** A delivery does not write domain data.
It rewinds the repository's cursor so the next sync re-reads that window, and
the REST API remains authoritative. A webhook payload can be partial, can arrive
out of order, and can be replayed; the API is complete and consistent. Treating
the payload as truth would make the data model depend on delivery order.

Webhooks also do not replace backfill. A webhook only reports events that happen
*after* it is configured, so historical synchronisation is still the only way to
learn about the past. The product needs both.

## Security

The receiver is a public URL — anyone can POST to it. Without verification,
anyone could invent deployments and pull requests, and **every metric in DevPulse
would be forgeable**.

- HMAC-SHA256 over the **raw body**, read before parsing. Re-serialising parsed
  JSON would not reproduce the bytes GitHub signed.
- Compared with `hmac.compare_digest`, which takes the same time whether the
  first or last byte differs. A plain `==` returns early on mismatch, and that
  timing difference is enough to recover a signature byte by byte.
- With no secret configured the endpoint returns **503 rather than accepting**
  unverified payloads.
- A delivery naming an untracked repository is **ignored, not auto-created** —
  otherwise anyone holding the secret could add repositories.
- `delivery_id` is unique, so GitHub's retries are recognised rather than
  double-counted.

## Two routers, deliberately

The receiver is public because GitHub cannot present a bearer token; its
signature *is* its authentication. The operator-facing event listing is mounted
with the protected group. Splitting them keeps that exception explicit instead
of leaving a public hole in a router someone later assumes is protected.

## Responding before processing

202, not 200. GitHub times out quickly and retries on timeout, so doing the work
before responding would turn one slow sync into duplicate deliveries.

## Verified live

Valid signature accepted and processed; a replayed delivery id recognised as a
duplicate; a forged signature rejected with 401; and a body altered after signing
rejected with 401.
