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
