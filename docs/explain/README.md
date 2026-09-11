# Understanding DevPulse, from scratch

This series explains every part of DevPulse assuming **no prior web development
knowledge**. It starts with what a web application even is and ends with you
being able to defend every design decision in the codebase.

Read them in order. Each one builds on the last.

| # | Chapter | What you will be able to explain |
|---|---|---|
| 01 | [What a web application is](01-what-is-a-web-application.md) | Browser, server, database, API, and why DevPulse is split in three |
| 02 | [The problem DevPulse solves](02-the-problem.md) | Why delivery data is scattered, and what "correlation" means |
| 03 | [Python and FastAPI](03-python-and-fastapi.md) | Routes, dependency injection, async, why FastAPI |
| 04 | [The database layer](04-database-orm-migrations.md) | Tables, SQL, ORM, migrations, why Alembic exists |
| 05 | [Pydantic and API contracts](05-pydantic-contracts.md) | Validation, serialisation, why schemas are separate from models |
| 06 | [Backend tour, file by file](06-backend-file-by-file.md) | What every one of the 62 backend files does |
| 07 | [The analytical engines](07-analytical-engines.md) | Every algorithm: correlation, DORA, baselines, bottlenecks, anomalies, conflicts, health |
| 08 | [The AI layer](08-ai-layer.md) | Evidence packages, structured output, hallucination guards |
| 09 | [React and the frontend](09-react-frontend.md) | Components, state, hooks, routing, TypeScript |
| 10 | [Frontend tour, file by file](10-frontend-file-by-file.md) | What every frontend file does |
| 11 | [Docker, Compose and CI](11-docker-and-ci.md) | Containers, images, orchestration, continuous integration |
| 12 | [Testing](12-testing.md) | Unit, API, component tests; why tests are written the way they are |
| 13 | [Security](13-security.md) | Hashing, tokens, HMAC, timing attacks, CORS |
| 14 | [Defending the project](14-defending-the-project.md) | Likely questions and honest answers |

---

## The one-paragraph summary

DevPulse connects to the tools a software team already uses (GitHub, CI,
deployment platforms, monitoring, incident management), pulls their data into
one database, works out which records describe the **same change**, reconstructs
that change's journey from commit to production, measures how long each step
took, compares it against history, and reports where delivery is slow or
breaking — **always stating what it cannot see** rather than guessing. AI sits
at the very end and only interprets facts the deterministic pipeline has
already established.

## The single most important idea

> **Missing data is reported as missing, never as zero.**

If DevPulse cannot see whether production is healthy, it says so. It never
reports "0 failures" when the truth is "no monitoring connected". Almost every
design decision in this codebase follows from taking that rule seriously — and
it came from a real bug, documented in
[`docs/architecture-audit.md`](../architecture-audit.md), where an empty
repository ranked as the *healthiest service* because absent data was scored as
a perfect record.
