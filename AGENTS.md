# DevPulse — AI Project Handbook

This file is the primary operating handbook for coding agents working on DevPulse.

`CLAUDE.md` must point to this file. Do not maintain a second independent agent handbook.

---

## 1. Mission

Build DevPulse into a mature engineering intelligence platform.

The product evolves through:

```text
Connect
→ Normalize
→ Correlate
→ Reconstruct
→ Measure
→ Compare
→ Detect
→ Explain
→ Recommend
```

The current phase stops before AI reasoning.

---

## 2. Source of Truth

Before making changes, inspect:

```text
PRD.md
architecture.md
Design.md
rules.md
testing.md
Decision.md
memory.md
```

If these documents conflict with code, inspect the current implementation and record the discrepancy before making architectural changes.

Never silently rewrite the product direction.

---

## 3. Current Repository

Expected structure:

```text
backend/
frontend/
infra/
docker-compose.yml
PRD.md
AGENTS.md
CLAUDE.md
architecture.md
Design.md
rules.md
testing.md
Decision.md
memory.md
```

The exact implementation may evolve.

Update architecture documentation when structure materially changes.

---

## 4. Development Principle

Use this order:

```text
Understand
→ Plan
→ Implement
→ Test
→ Verify
→ Document
→ Commit
→ PR
```

Do not code first and rationalize afterward.

---

## 5. Hard Rule: AI Is Deferred

Do not implement:

- LLM RCA
- AI bottleneck detection
- AI anomaly detection
- AI recommendations
- RAG
- embeddings
- vector databases
- autonomous agents

until the deterministic evidence pipeline is complete.

---

## 6. Deterministic Core

The following must use ordinary application logic:

- ingestion
- normalization
- correlation
- delivery traces
- DORA
- historical baselines
- anomaly detection
- bottleneck detection
- data coverage
- pipeline mapping
- conflict detection

---

## 7. Connector Rule

Connectors collect and map provider data.

They must not contain:

- DORA calculations
- RCA
- frontend logic
- bottleneck scoring

Provider data should flow through:

```text
Provider
→ Connector
→ Normalizer
→ Event Model
→ Correlation
→ Analytics
```

---

## 8. Before Every Stage

Inspect the repository.

Identify:

- affected files
- dependencies
- database implications
- API implications
- frontend implications
- migration requirements
- test strategy

Then implement only the approved stage.

---

## 9. PR Discipline

Development is PR-driven.

Create coherent PRs frequently.

A PR should have:

```text
What changed
Why
Implementation
Validation
Limitations
Next
```

Do not mix unrelated refactors into feature PRs.

---

## 10. Validation

Never trust a feature because it compiles.

Run the relevant:

```text
unit tests
integration tests
API tests
frontend tests
E2E tests
Docker validation
manual verification
```

depending on the stage.

---

## 11. Security

Never commit secrets.

Never bypass GitHub secret scanning.

Use environment variables and proper secret handling.

Never put realistic token examples into documentation.

---

## 12. Missing Data

Missing telemetry must remain visible.

Do not transform:

```text
unknown
```

into:

```text
healthy
```

Do not transform:

```text
CI success
```

into:

```text
production deployment success
```

unless the system explicitly establishes that relationship.

---

## 13. Correlation

Prefer strong identifiers:

1. commit SHA
2. deployment revision
3. artifact/image digest
4. PR/workflow IDs
5. service/application identity
6. environment
7. timestamps as supporting evidence

Never infer causality solely from time proximity.

---

## 14. Documentation

When an architectural decision is made:

1. Record it in `Decision.md`.
2. Record important current state in `memory.md`.
3. Update `architecture.md` if structure changes.
4. Update `testing.md` if testing strategy changes.

---

## 15. Required Agent Response

For every completed stage, report:

```text
Stage
Goal
Implementation
Files changed
Database changes
API changes
Frontend changes
Tests run
Manual validation
Known limitations
Decision records added
Next stage
```

Then stop unless instructed to continue.
