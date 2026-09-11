# 12 · Testing

## Why DevPulse is heavily tested

Most of this product is **arithmetic you cannot eyeball**. If the bottleneck
score is 88.7 instead of 62.1, nothing looks wrong on screen — a plausible
number appears either way. You cannot click your way to confidence in a median.

So the guiding principle in `testing.md` is:

> **Known input must produce known analytical output.**

Current state: **218 backend tests, 29 frontend tests.**

## Running them

```bash
cd backend && ./.venv/bin/python -m pytest        # 218 passed
cd frontend && npm test                           # 29 passed
```

## pytest and fixtures

A test is a function whose name starts with `test_`:

```python
def test_median_resists_a_single_outlier_where_a_mean_would_not():
    values = [7, 7, 8, 6, 7, 4000]
    baseline = summarise(values)

    assert baseline.median_value == 7.0
    assert sum(values) / len(values) > 600   # the mean is destroyed
```

A **fixture** is reusable setup, requested by naming it as a parameter:

```python
@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool, ...)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_something(db_session):     # ← pytest supplies it
    ...
```

Each test gets a **fresh in-memory database**. Tests cannot affect each other,
and the suite runs in seconds because nothing touches disk.

`StaticPool` is needed because SQLite would otherwise hand out a *new empty
database* per connection.

## Three fixtures worth understanding

### `isolated_settings` — hermetic by force

```python
@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False, raising=False)
    monkeypatch.setattr(settings, "prometheus_url", "", raising=False)
    monkeypatch.setattr(settings, "auth_enabled", False, raising=False)
    ...
```

`autouse=True` means it runs for every test without being requested. It exists
because five tests once passed in CI and failed locally, purely because a
developer's `.env` had `DEMO_MODE=true`.

Anything needing a provider switched on turns it on **explicitly**.

### `NOW` — time that cannot drift

```python
NOW = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
```

The metrics engine derives its look-back window from the wall clock. A test
using absolute timestamps would silently drift out of that window as weeks
passed and start failing for no reason. Every test event is positioned as an
**offset from `NOW`**.

### `RunBuilder` — readable timelines

```python
runs.add(workflow_name="CI", conclusion="failure", started_minutes_ago=60)
runs.add_merged_pr(number=482, merged_minutes_ago=140)
```

Tests read as a story rather than a wall of timestamps.

It also carries a small lesson: `github_run_id` is globally unique, so ids come
from one counter shared across every builder. The first version restarted at 1
per builder, and a test using two repositories hit a constraint violation.

## What the tests actually assert

### Ground truth from the PRD

```python
GROUND_TRUTH_LEAD_TIME_MINUTES = 75.0   # PRD §5: merged 10:00, deployed 11:15

def test_measures_merge_to_the_deployment_that_shipped_the_commit(...):
    ...
    assert metrics.lead_time_hours == pytest.approx(75.0 / 60.0, abs=0.01)
```

The specification's worked example is asserted directly.

### What must NOT happen

Most valuable tests are negative:

```python
def test_a_run_with_a_different_commit_is_never_attached(...)
def test_an_improvement_is_not_an_anomaly(...)
def test_stable_runtime_after_a_deployment_raises_no_conflict(...)
def test_a_dimension_with_no_data_scores_null_not_zero(...)
def test_an_unknown_email_and_a_wrong_password_are_indistinguishable(...)
```

Each encodes a way the product could quietly become wrong.

### Behaviour-oriented names

From `testing.md` §24. Compare:

```text
test_1                                    tells you nothing
test_ci_regression                        vaguely
test_a_ci_run_is_not_counted_as_a_production_deployment   ← the spec, in a name
```

When one fails, the name alone tells you what broke.

## `xfail` — defects as executable specifications

This is the most unusual technique in the suite (ADR-016).

When the audit found defects, they were encoded as tests asserting the behaviour
the product *required*, marked expected-to-fail:

```python
@pytest.mark.xfail(strict=True, reason=
    "ADR-010: every workflow run is treated as a deployment. "
    "Only 6 of 34 counted deployments were deployment-shaped. Fixed by Stage 5.")
def test_a_ci_run_is_not_counted_as_a_production_deployment(...):
    assert metrics.total_deployments == 1
```

The suite stays green while the defect stands. `strict=True` means that **the
moment the defect is fixed, the test fails** — forcing the marker to be removed
and the fix acknowledged.

A defect could not be silently fixed, and could not be silently reintroduced.
All three markers were removed when Stage 5 landed; the suite went from
*166 passed, 3 xfailed* to *169 passed, 0 xfailed*.

## Mocking external services

Connector tests must not call GitHub: slow, rate-limited, and dependent on
someone's network. `respx` intercepts HTTP:

```python
@respx.mock
def test_an_authentication_failure_is_recorded_instead_of_disappearing(...):
    respx.get(PULLS_URL).mock(return_value=httpx.Response(401, ...))

    job = sync_repository(db_session, "devpulse-test/payments-api", client)

    assert job.status == SyncStatus.FAILED
    assert job.error_code == ErrorCode.AUTHENTICATION_ERROR.value
```

That test recreates the exact scenario the audit found — where a 401 vanished
entirely — and asserts it is now recorded.

A `respx` subtlety worth knowing: a route registered for a bare path also matches
the paginated URL, so a two-page test initially replayed page one forever. The
fix was one route keyed on the query string.

## Frontend testing

**Vitest** (test runner) and **React Testing Library**, which queries the DOM the
way a *user* would — by visible text and accessible roles, not CSS classes:

```tsx
it("renders a null value as Unavailable, never as zero", () => {
  render(<MetricCard label="Runtime Health" value={null} />);

  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.queryByText("0")).not.toBeInTheDocument();
});
```

`getByText` throws if absent; `queryByText` returns null. Use `query` when
asserting absence.

A test refactor worth noting: `getByText("Sign in")` failed because "Sign in"
was both the heading and the button. `getByRole("button", { name: /sign in/i })`
is unambiguous — and closer to how a user identifies it.

`vitest.setup.ts` stubs `ResizeObserver`, which jsdom lacks and Recharts needs.

## What is not tested

Honesty matters here too:

- **No end-to-end tests.** Playwright driving a real browser through the full
  stack is planned, not built.
- **No real-model AI tests.** Deliberate — a `FakeProvider` is used, because what
  is under test is DevPulse's handling of output, not the model.
- **Unit tests run on SQLite, not PostgreSQL.** Migrations are verified against
  real PostgreSQL in CI instead. Anything depending on PostgreSQL-specific
  behaviour needs an integration test, which does not exist yet.

---

**Next:** [13 · Security](13-security.md)
