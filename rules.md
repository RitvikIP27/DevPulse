# DevPulse — Engineering Rules

## 1. Naming

### Python

Use:

```python
snake_case
```

Classes:

```python
PascalCase
```

Constants:

```python
UPPER_SNAKE_CASE
```

### TypeScript

Variables/functions:

```text
camelCase
```

Components/types:

```text
PascalCase
```

Constants:

```text
UPPER_SNAKE_CASE
```

---

# 2. Naming Must Describe Meaning

Prefer:

```python
deployment_started_at
```

over:

```python
time1
```

Prefer:

```typescript
historicalBaseline
```

over:

```typescript
oldData
```

---

# 3. No Magic Numbers

Bad:

```python
if duration > 300:
```

Good:

```python
BOTTLENECK_THRESHOLD_SECONDS = 300
```

Or derive thresholds from documented logic.

---

# 4. Time Handling

Use timezone-aware timestamps at system boundaries.

Normalize external timestamps consistently.

Do not silently mix local time and UTC.

Store timestamps in a consistent database representation.

---

# 5. IDs

Prefer provider IDs as external identifiers.

Use internal database IDs as DevPulse identifiers.

Never assume two vendors use the same ID namespace.

---

# 6. API Routes

Routes should be thin.

Bad:

```python
@router.get(...)
def endpoint(...):
    # 200 lines of business logic
```

Good:

```text
route
 ↓
service
 ↓
domain/data layer
```

---

# 7. Connector Rules

Connectors:

- fetch
- validate
- paginate
- normalize
- report errors

Connectors do not:

- calculate DORA
- determine bottlenecks
- perform RCA
- render UI

---

# 8. Analytics Rules

Analytics must be deterministic.

A calculation should be reproducible from the same data.

Document non-obvious formulas.

---

# 9. Correlation Rules

Never use time proximity as the only proof of identity.

Prefer:

```text
commit SHA
deployment revision
artifact digest
workflow ID
service
environment
```

Record correlation evidence.

---

# 10. Causality Rules

Never claim:

```text
X caused Y
```

merely because:

```text
X happened before Y
```

Use:

```text
observed after
correlated with
potential contributor
likely
```

until evidence supports stronger language.

---

# 11. Missing Data Rules

Never convert:

```text
unknown
```

into:

```text
success
```

Never fabricate:

- deployments
- incidents
- runtime health
- recovery times
- DORA values

---

# 12. AI Rules

Until the AI milestone is explicitly approved:

```text
NO AI
```

When AI is introduced:

- AI cannot invent telemetry.
- AI cannot replace deterministic calculations.
- AI output must identify uncertainty.
- AI recommendations must cite evidence.
- AI must operate on structured evidence.

---

# 13. Database Rules

Use migrations.

Do not manually alter production-like schemas without migration history.

Avoid destructive migrations during feature development.

Prefer nullable/additive migration paths when evolving an MVP.

---

# 14. Frontend Rules

Use reusable components.

Avoid putting all application state into one component.

Avoid duplicated API logic.

Centralize API client behavior.

Every async screen should account for:

```text
loading
success
empty
error
```

---

# 15. CSS Rules

Use design-system variables from `Design.md`.

Do not scatter arbitrary colors throughout components.

Do not introduce a second visual language.

---

# 16. Dependency Rules

Before adding a dependency, ask:

1. What problem does it solve?
2. Can existing tooling solve it?
3. Does it increase maintenance cost?
4. Is it justified by current scale?

Do not add technology for resume decoration.

---

# 17. Logging

Logs should answer:

```text
what happened
which resource
which provider
which operation
whether it succeeded
why it failed
```

Never log secrets.

---

# 18. Secrets

Never commit secrets.

Never place real tokens in:

- README
- examples
- tests
- fixtures
- source code
- logs

Use environment variables and secret management.

---

# 19. PR Rules

Each PR must have a coherent purpose.

Preferred prefixes:

```text
feat:
fix:
refactor:
test:
docs:
chore:
```

No unrelated work.

---

# 20. Git Rules

Before pushing:

```text
git status
git diff
tests
build
```

Inspect the diff.

Never bypass secret scanning.

---

# 21. Refactoring Rules

Do not perform broad refactors during feature work unless the refactor is necessary.

If a refactor is required:

- explain why
- keep scope controlled
- test before/after behavior

---

# 22. Documentation Rules

Architectural changes update:

```text
architecture.md
Decision.md
memory.md
```

Testing changes update:

```text
testing.md
```

Product changes update:

```text
PRD.md
```

---

# 23. Comments

Comment why, not what.

Bad:

```python
# increment i
i += 1
```

Good:

```python
# GitHub pagination is capped to avoid unbounded historical requests.
```

---

# 24. Quality Standard

Code should be:

- readable
- testable
- explicit
- maintainable
- boring where boring is appropriate

Prefer clarity over cleverness.
