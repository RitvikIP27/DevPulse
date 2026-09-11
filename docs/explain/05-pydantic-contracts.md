# 05 · Pydantic and API contracts

## The problem

Data arriving from outside cannot be trusted. A request body might be missing a
field, have a string where a number belongs, or contain a password of two
characters. Checking all that by hand produces defensive code everywhere:

```python
if "email" not in body: return error(422)
if not isinstance(body["email"], str): return error(422)
if len(body.get("password", "")) < 12: return error(422)
```

## Pydantic

**Pydantic** replaces that with a declaration. From
`backend/app/schemas/auth.py`:

```python
class RegisterRequest(BaseModel):
    email: Email
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=72)
    display_name: str | None = Field(default=None, max_length=120)
```

FastAPI now validates every request against this **before** the route runs.
Malformed input never reaches your code — it gets a `422` with a precise
explanation of what was wrong.

`str | None` means "a string, or nothing". That is Python's way of saying
optional, and it maps to `nullable` in the database and `string | null` in
TypeScript. The same idea travels the whole stack.

## Models vs schemas: why two sets of classes?

DevPulse has `models/events.py` (SQLAlchemy, database) **and** `schemas/*.py`
(Pydantic, API). Beginners reasonably ask why not one.

Because they answer different questions.

```text
   models/events.py              schemas/repositories.py
   ────────────────              ───────────────────────
   "how is this STORED?"         "what does the API PROMISE?"

   User.password_hash            never appears in any schema
   Repository.id                 exposed as id
   Repository.last_synced_at     reshaped into LastSync
                                 + correlatable_run_pct (computed, not stored)
```

Three concrete consequences:

**1. Secrets cannot leak.** `User` has `password_hash`. `UserOut` does not. Even
if someone returned a raw `User` from a route, `response_model=UserOut` strips
everything not declared. The schema is a filter, not a suggestion.

**2. The API can present data differently from storage.** `RepositorySummary`
includes `correlatable_run_pct`, which is calculated at request time and stored
nowhere.

**3. Storage can change without breaking clients.** Rename a column, adjust the
schema mapping, and the frontend never notices.

## Enums: making illegal states unrepresentable

From `backend/app/schemas/repositories.py`:

```python
class CoverageStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NO_DATA = "NO_DATA"
    NOT_CONFIGURED = "NOT_CONFIGURED"
```

An **enum** is a fixed set of allowed values. `status = "avilable"` is now a
crash at the boundary, not a subtly broken UI.

More importantly, this enum **encodes the honesty rule in the type system**:

- `AVAILABLE` — we are watching and have data
- `NO_DATA` — we are watching and have seen nothing
- `NOT_CONFIGURED` — we are not watching at all

The last two are the ones every naive dashboard collapses into "0". Here they
are separate values, so collapsing them requires a deliberate act.

The same technique appears in `schemas/conflicts.py`:

```python
class RelationStrength(str, Enum):
    CORRELATED = "CORRELATED"
    POTENTIALLY_RELATED = "POTENTIALLY_RELATED"
```

There is **no `CAUSED`**. Not because it is discouraged — because it does not
exist. You cannot assert causation through this API, because the vocabulary to
do so was never defined. That is a stronger guarantee than a code review comment.

## Nullable metrics and reasons

`backend/app/schemas/metrics.py`:

```python
class ServiceDoraMetrics(BaseModel):
    service: str
    deployment_source: str
    unavailable_reason: str | None = None

    deployment_frequency_per_week: float | None
    lead_time_hours: float | None
    change_failure_rate_pct: float | None
    failed_deployment_recovery_hours: float | None
    deployment_rework_rate_pct: float | None
```

**Every metric is nullable.** A metric that cannot be computed returns `None`,
paired with `unavailable_reason` explaining why in a sentence a human can read:

> "No deployment provider is connected and no deployment workflow has been
> configured, so DevPulse cannot identify production deployments."

The frontend then renders `—` with that explanation rather than a misleading `0`.

## Nested schemas

Schemas compose:

```python
class RepositorySummary(BaseModel):
    id: int
    full_name: str
    coverage: RepositoryCoverage      # ← another schema

class RepositoryCoverage(BaseModel):
    stages: list[StageCoverage]       # ← a list of another schema
    confidence: AnalysisConfidence
    confidence_reason: str
```

This produces nested JSON, validated all the way down — and it is how the
`EvidencePackage` (chapter 08) can be one object containing the output of six
different engines.

## Why this matters for the AI layer

`backend/app/schemas/rca.py` uses Pydantic for something unusual: constraining a
language model.

```python
class RcaResult(BaseModel):
    summary: str
    likely_cause: str
    confidence: RcaConfidence
    observed_facts: list[str]
    inferences: list[str]
    alternative_hypotheses: list[Hypothesis]
    unknowns: list[str]
```

This schema is sent to the model as its required output format. It cannot reply
with a paragraph of prose. It must separate `observed_facts` from `inferences`,
must supply `alternative_hypotheses`, and must fill in `unknowns`.

Prose is where unsupported certainty hides. A schema forces the model to commit
to which category each statement belongs in.

## Every schema file

| File | Contract for |
|---|---|
| `metrics.py` | The five DORA metrics |
| `repositories.py` | Repositories, pipeline stages, coverage, confidence |
| `deliveries.py` | Delivery traces, stage statuses, correlation evidence |
| `deployment_rules.py` | Declaring which workflow deploys |
| `sync.py` | Ingestion job outcomes |
| `bottlenecks.py` | Stage analysis and score components |
| `anomalies.py` | Detected deviations |
| `conflicts.py` | Runtime comparison and cross-system conflicts |
| `health.py` | Composite scoring dimensions |
| `evidence.py` | The package handed to AI |
| `rca.py` | The structure the model must return |
| `auth.py` | Registration, login, tokens |

---

**Next:** [06 · Backend tour, file by file](06-backend-file-by-file.md)
