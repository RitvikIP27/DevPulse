# DevPulse — Testing Strategy

## 1. Testing Philosophy

Testing must prove that DevPulse is correct, not merely that it runs.

The most important testing principle is:

> **Known input must produce known analytical output.**

---

# 2. Testing Pyramid

```text
                 E2E
              Playwright
                 ▲
                 │
          Integration Tests
                 ▲
                 │
            API Tests
                 ▲
                 │
             Unit Tests
                 ▲
                 │
        Deterministic Logic
```

Use the cheapest reliable test level first.

---

# 3. Unit Tests

Primary scope:

- normalization
- timestamp parsing
- correlation
- DORA calculations
- baseline calculations
- bottleneck scoring
- anomaly detection
- coverage calculations
- health scoring
- conflict detection

Backend framework:

```text
pytest
```

Example:

```python
def test_change_lead_time():
    ...
```

---

# 4. Integration Tests

Test multiple components together.

Examples:

```text
GitHub fixture
 ↓
connector
 ↓
normalizer
 ↓
database
```

or:

```text
normalized events
 ↓
correlation
 ↓
delivery trace
```

Use:

```text
pytest
```

with a test PostgreSQL environment where database behavior matters.

---

# 5. API Tests

Test FastAPI endpoints.

Validate:

- status codes
- response schemas
- filters
- pagination
- validation
- missing data
- errors

Example:

```text
GET /api/metrics/dora
GET /api/deliveries/{id}
POST /api/repositories/{id}/sync
```

Use FastAPI's test client / HTTP client tooling.

---

# 6. Frontend Unit Tests

Use:

```text
Vitest
```

Test:

- components
- formatting
- metric rendering
- loading states
- error states
- empty states
- utility functions

---

# 7. Frontend Component Tests

Use:

```text
React Testing Library
```

Focus on user behavior rather than implementation details.

Example:

```text
given loading state
→ spinner shown

given unavailable metric
→ unavailable state shown

given bottleneck
→ bottleneck evidence displayed
```

---

# 8. End-to-End Testing

Use:

```text
Playwright
```

Critical journeys:

### Repository onboarding

```text
Open app
→ Repositories
→ Add repository
→ Configure
→ Sync
→ See repository data
```

### Delivery trace

```text
Open Deliveries
→ select delivery
→ view pipeline
→ inspect stage
```

### Bottleneck

```text
Open Bottlenecks
→ inspect bottleneck
→ inspect evidence
```

---

# 9. Contract Tests

Connector outputs should be validated against normalized event schemas.

Example:

```text
GitHub adapter
→ expected DevPulse event shape
```

This prevents provider API changes from silently corrupting analytics.

---

# 10. Connector Tests

Each connector should test:

- authentication failure
- successful request
- pagination
- empty response
- rate limiting
- timeout
- malformed response
- partial failure
- duplicate event handling

Use fixtures/mocks rather than depending on external services for every CI run.

---

# 11. Correlation Tests

Test strong identifiers.

Example:

```text
commit abc123
PR abc123
CI abc123
deployment abc123
```

must produce one delivery.

Test non-matches too.

Example:

```text
commit abc123
deployment xyz999
```

must not be incorrectly correlated.

---

# 12. DORA Tests

Every DORA calculation needs ground-truth tests.

Example:

```text
commit = 10:00
production deployment = 11:15

expected lead time = 75m
```

Test:

- normal case
- no deployment
- multiple deployments
- failed deployment
- rollback
- missing timestamps
- timezone boundaries

---

# 13. Bottleneck Tests

Create synthetic stage durations.

Example:

```text
Review       300m
CI             8m
Build          2m
Deploy         3m
```

Expected:

```text
Review = primary bottleneck
```

Also test cases where:

- failure rate dominates
- queue time dominates
- multiple stages are similar
- data is insufficient

---

# 14. Historical Analytics Tests

Given known historical values:

```text
7, 7, 8, 6, 7
```

and current:

```text
24
```

verify:

- median
- deviation
- trend
- regression classification

---

# 15. Conflict Tests

Example:

```text
Deployment = SUCCESS
Kubernetes = SUCCESS
Runtime = DEGRADED
Incident = YES
```

Expected:

```text
deployment/runtime conflict detected
```

Do not classify this as a generic deployment failure.

---

# 16. Missing Data Tests

If runtime telemetry is absent:

Expected:

```text
runtime status = unavailable
```

and:

```text
analysis coverage = reduced
```

Never return fabricated runtime health.

---

# 17. Synthetic Reference Pipeline

Maintain:

```text
devpulse-demo-pipeline
```

with:

- FastAPI
- Docker
- GitHub Actions
- Kubernetes

It must support controlled test scenarios.

---

# 18. Scenario Testing

Required scenarios:

## Healthy

```text
PR → CI → deployment → healthy runtime
```

## Review bottleneck

Long review delay.

Expected:

```text
review bottleneck
```

## CI bottleneck

Artificial CI delay.

Expected:

```text
CI regression/bottleneck
```

## Failed deployment

Deployment fails.

Expected:

```text
deployment failure
```

## Recovery

Failure → recovery.

Expected:

```text
recovery duration
```

## Runtime regression

Deployment succeeds, runtime degrades.

Expected:

```text
deployment success + runtime degradation
```

## Conflicting systems

Control plane succeeds, monitoring fails.

Expected:

```text
conflict detected
```

## Missing telemetry

Monitoring unavailable.

Expected:

```text
partial analysis
```

---

# 19. C2C / End-to-End Validation

The full delivery path should eventually be testable:

```text
PR
 ↓
CI
 ↓
Build
 ↓
Deployment
 ↓
Runtime
 ↓
DevPulse ingestion
 ↓
Normalization
 ↓
Correlation
 ↓
Analytics
 ↓
Dashboard
```

This is the highest-value product test.

---

# 20. Test Data

Maintain deterministic fixtures for:

- PRs
- commits
- workflow runs
- deployments
- runtime observations
- incidents

Fixtures must be safe and contain no credentials.

---

# 21. Frontend Tooling

Preferred:

```text
Vitest
React Testing Library
Playwright
```

---

# 22. Backend Tooling

Preferred:

```text
pytest
FastAPI TestClient / HTTP client
SQLAlchemy test database
```

---

# 23. CI

Every PR should eventually run:

```text
lint
type checking
unit tests
integration tests
frontend tests
build
```

E2E may run in a dedicated CI job depending on runtime cost.

---

# 24. Test Naming

Use behavior-oriented names.

Good:

```text
test_deployment_failure_is_not_counted_as_successful_deployment
test_runtime_degradation_after_successful_rollout_is_detected
test_unavailable_monitoring_reduces_analysis_coverage
```

Bad:

```text
test_1
test_function
test_data
```

---

# 25. Regression Rule

Every production bug that reaches the repository should gain a regression test.

---

# 26. Definition of Testing Done

A feature is not done when code compiles.

It is done when:

```text
unit
+
integration
+
API
+
UI
+
E2E where appropriate
+
manual validation
```

provide sufficient confidence for that feature.

---

# 27. Implementation Status

> Updated 2026-09-10 (Stage 0.5). Keep current as the suite grows.

## What exists

```text
backend/pytest.ini            pytest configuration + custom markers
backend/requirements-dev.txt  test-only dependencies, kept out of the runtime image
backend/tests/conftest.py     fixtures: db_session, api_client, repository, runs
backend/tests/test_dora_metrics.py   metric arithmetic + locked known defects
backend/tests/test_api.py            HTTP contract tests
```

Current result: **17 passed, 3 xfailed**.

## Database strategy

Unit and API tests run against **in-memory SQLite**. The MVP models use only
generic column types, so this is faithful and fast (section 2: cheapest reliable
level first). Tables are created from `Base.metadata`, not by running migrations.

This has a limit worth stating plainly: SQLite cannot represent everything a
migration or a PostgreSQL-specific type can. So **migrations are verified
separately against real PostgreSQL in CI** — applied to an empty database,
downgraded to base, then checked for model/migration drift via autogenerate.

When a feature depends on real PostgreSQL behaviour — JSON containment,
concurrent upserts, constraint semantics — it needs an integration test against
a live database (section 4), not a SQLite unit test.

## Time in tests

The metrics engine derives its look-back window from the wall clock. Test events
are therefore positioned as offsets from a single `NOW` captured at import
(`tests/conftest.py`), never as absolute timestamps, so the suite cannot drift
out of its own window as real time passes.

## The `known_defect` marker

Per ADR-016, a defect proven by the audit is encoded as a test asserting the
*required* behaviour, marked `xfail(strict=True)` with the fixing stage named in
the reason.

**When a stage fixes one of these, the test will fail.** That is the design.
Remove the `xfail` and `known_defect` markers, keep the assertion, and update
`memory.md`.

Currently locked:

```text
test_a_ci_run_is_not_counted_as_a_production_deployment     -> Stage 5
test_lead_time_measures_merge_to_production_deployment      -> Stage 7
test_a_repository_with_no_data_reports_unavailable_not_zero -> Stage 6
```

## Not yet built

```text
connector tests (respx is installed and ready)
integration tests against PostgreSQL
frontend tests (Vitest / React Testing Library)
E2E (Playwright)
the devpulse-demo-pipeline synthetic repository
```
