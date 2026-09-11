# 07 · The analytical engines

Every algorithm in DevPulse, in the order they build on each other.

```text
  correlation ──► delivery traces ──► baselines ──► bottlenecks
                        │                 │              │
                        │                 └──► anomalies │
                        ▼                                │
                  deployments ──► DORA metrics           │
                        │                                │
                        └──► runtime comparison ──► conflicts
                                                         │
                     everything above ──► health ──► evidence ──► AI
```

---

## 1 · Correlation (`services/deliveries.py`)

**Question:** which records describe the same change?

**Method:** exact commit-SHA matching. A merged pull request has a
`merge_commit_sha`; workflow runs have a `head_sha`. Equal SHAs mean the same
code.

```python
def _runs_for(db, repo_id, commit_sha):
    return (
        db.query(WorkflowRun)
        .filter(WorkflowRun.repository_id == repo_id)
        .filter(WorkflowRun.head_sha == commit_sha)
        .order_by(WorkflowRun.started_at.asc())
        .all()
    )
```

**What it refuses to do:** use time. A run starting one second after a merge but
carrying a different commit is left unlinked. There is a test named
`test_a_run_with_a_different_commit_is_never_attached` asserting exactly that,
because this is the mistake that broke the original lead-time metric.

**Output:** a trace of ten stages, each `SUCCESS`, `FAILED`, `IN_PROGRESS` or
`NOT_OBSERVED`. Every trace carries its own correlation evidence:

> "10 workflow run(s) reported head_sha 13be8d5bc3, exactly matching the merge
> commit of pull request #27. Matched on commit identity, not timestamp
> proximity."

**Derived, not stored** (ADR-020). The inputs are already in the database and
the computation is deterministic, so changing the correlation rules takes effect
immediately instead of requiring a backfill.

---

## 2 · Deployments (`services/deployments.py`)

**Question:** which records are *real production deployments*?

This is the question the original MVP got wrong, and the audit measured the
damage: **only 6 of 34** counted "deployments" were deployment-shaped, and
deployment frequency was overstated by roughly **5.7×**.

**Two sources, in order of authority, never mixed:**

1. `github_deployments` — the provider's own Deployments API. Authoritative.
2. `configured_workflow` — a rule a human declared naming which workflow deploys.

If the provider supplied any deployment, rule-derived rows are ignored. Blending
an authoritative source with a declared one produces a number nobody can explain.

**If neither exists, every deployment-derived metric reports `null` with a
reason.** There is no fallback to counting CI runs.

**Why not match workflow names containing "deploy"?** Because that recreates the
original bug in a subtler form. On the audited repository that substring also
matches *infrastructure* workflows. Heuristics were the defect; explicit
configuration (ADR-009) is the fix.

**Measured effect** of configuring the real CD workflow:

| Metric | CI proxy | Real deployments |
|---|---|---|
| Deployment frequency | 2.64/wk | **0.47/wk** (5.6× correction) |
| Change fail rate | 21.3% | **53.8%** |
| Lead time | 0.0h | **5m** |

The 5.6× correction closely matched the 5.7× the audit predicted — a useful
confirmation the audit measured the right thing. The fail rate went *up*,
because the CD workflow genuinely fails more than the CI runs diluting it.

---

## 3 · DORA metrics (`services/dora_metrics.py`)

The five metrics current DORA defines:

| Metric | How DevPulse computes it |
|---|---|
| Deployment frequency | Successful production deployments ÷ weeks |
| Change lead time | Median from PR merge → the deployment carrying **that same commit** |
| Change fail rate | Failed ÷ concluded production deployments |
| Failed deployment recovery | Median failed → next successful deployment |
| Deployment rework rate | Share of deployments that remediated a previous failure |

**Lead time is matched by commit, not time order.** That single sentence is the
correction: the MVP took "the next successful run after a merge", which was
always the CI job the merge triggered.

**Recovery has a window.** A success more than 48 hours after a failure is not
treated as its recovery — calling it one would invent a causal link between two
unrelated deployments.

**Rework rate is honest about being a lower bound.** DevPulse can only see
remediation that followed an *observed* deployment failure. Rework prompted by a
user-reported bug that never failed a deployment is invisible without incident
data, and the UI says so.

**Ranking:** worst-performing first — but services that cannot be measured sort
**last**, not first. An unmeasurable service is not a healthy one. (This is the
audit bug, fixed.)

---

## 4 · Baselines (`services/baselines.py`)

**Question:** what is normal for this metric?

**Median, not mean.** Delivery data is heavily skewed. On the audited repository
CI has a **median of 4.2 minutes and a p90 of 609 minutes** — one run left
queued over a weekend. A mean would describe neither number.

```python
def summarise(values: list[float]) -> Baseline:
    centre = median(usable)
    return Baseline(
        sample_count=len(usable),
        median_value=round(centre, 2),
        p90_value=round(_percentile(usable, 0.9) or centre, 2),
        mad=round(median([abs(v - centre) for v in usable]), 2),
    )
```

**MAD** (median absolute deviation) is the robust analogue of standard
deviation: the typical distance from the middle, itself measured by a median so
one outlier cannot inflate it.

**Refusals are part of the design:**

| Condition | Result |
|---|---|
| Fewer than 5 baseline samples | No comparison, with the reason stated |
| Baseline median is zero | Percentage change is undefined, said so |
| Change below 25% | Normal variation, not a regression |

*"Not enough history"* and *"no regression"* are **different claims**. Collapsing
them is how a dashboard starts lying quietly.

---

## 5 · Bottlenecks (`services/bottlenecks.py`)

**Question:** where is delivery time going?

**The naive answer is wrong.** "The slowest stage is the bottleneck" ignores
that a stage which has *always* taken twenty minutes is a cost, not a
constraint. The stage that used to take five and now takes forty is where
delivery is being lost — even though it is not the slowest.

**Four weighted signals:**

```text
latency contribution   0.40   share of total measured delivery time
historical regression  0.25   change vs the immediately preceding period
failure impact         0.20   share of observations that failed
frequency              0.15   share of deliveries passing through
```

**Weights renormalise over available signals.** With no baseline the regression
component is dropped and the rest rescale to sum to 1.0. Scoring a missing
baseline as zero would penalise a genuinely constrained stage for the accident
of having no history.

**Every score decomposes.** Each component returns its value, weight,
contribution and an explaining sentence, and the UI renders that breakdown:

```text
CI · HIGH impact · Regression · 88.7 / 100
  Latency contribution  weight 0.4   +39.8
    This stage accounts for 99.5% of all measured delivery time.
  Historical regression weight 0.25  +25.0
    Median moved from 3.25m to 11.5m (+253.8%).
```

PRD constraint 9 requires this. The practical reason: an engineer shown "88.7"
asks *why*, and a page that cannot answer loses the argument.

**Refuses to conclude** below 3 deliveries, returning the count and why that is
too few.

---

## 6 · Anomalies (`services/anomalies.py`)

**Question:** what changed *recently*? Distinct from bottlenecks — a stage can be
the biggest cost without anything having moved.

Compares a short recent window against the three periods before it, using the
**same** `baselines.py` primitives. That shared module is why both pages report
the identical +253.8%.

**Conservatism is the design:**

| Rule | Reason |
|---|---|
| Change < 25% | Normal variation (same threshold as bottlenecks) |
| < 5 baseline samples | Nothing claimed |
| **Improvements are never anomalies** | CI getting 3× faster is good news; flagging it trains people to ignore the page |
| Severity banded on magnitude | HIGH ≈ a tripling or worse |

A surface that cries wolf gets ignored, and an ignored surface is worse than
none: it costs attention and returns nothing.

**Persisted, not derived.** A derived-only anomaly cannot answer "when did this
start?", cannot be acknowledged, and vanishes the moment the metric recovers.

**Idempotence** matters because detection runs on every page load. The
uniqueness key is `(repository, metric, window_start)` with `window_start`
truncated to the hour. Untruncated, every run was a distinct window and inserted
a duplicate — caught by a test asserting two runs leave one row.

---

## 7 · Runtime comparison and conflicts (`services/conflicts.py`)

**This is the differentiating feature.**

A deployment platform reporting `SUCCESS` is describing **its own control
plane**. It knows the rollout mechanism finished. It knows nothing about whether
the application still works.

**Method:** compare runtime metric medians in a window before the deployment
against the same window after.

```text
Control plane: SUCCESS    Runtime: Degraded    1 incident
  error_rate_pct   0.8 →  18.4   +2200%
  latency_p95_ms   180 →   910   +405.6%
```

**Never causation.** The strength vocabulary is closed:

```python
class RelationStrength(str, Enum):
    CORRELATED = "CORRELATED"
    POTENTIALLY_RELATED = "POTENTIALLY_RELATED"
```

There is no `CAUSED`. A test asserts the word never appears in generated
evidence except inside an explicit *unknown*. Every conflict renders:

> **Not determined:** Whether the deployment caused the degradation, or the two
> merely coincided. Whether an external dependency degraded at the same time.

**False-positive guards:**

| Guard | Why |
|---|---|
| < 3 samples either side | Two points is an anecdote, not a shift |
| Worsening < 50% | Noise |
| Direction is per-metric | Higher is worse for error rate, better for availability |
| Incident > 60 min after | Not associated |
| Nothing to report | Deployment omitted, so the page shows signal |

---

## 8 · Health (`services/health.py`)

**Question:** overall, how healthy is this service?

Five dimensions, each the mean of named bounded inputs:

```text
DELIVERY       deployment frequency, lead time
STABILITY      change fail rate, recovery time
PIPELINE       CI failure rate, CI duration trend
RUNTIME        share of deployments without a runtime conflict
OBSERVABILITY  how many delivery stages report data at all
```

**A dimension with no measurable input scores `null`, not zero.** Zero means "we
measured and it is bad"; null means "we cannot see".

**Overall averages only scorable dimensions** — a team is never marked down for
DevPulse's own blind spots.

**OBSERVABILITY scores DevPulse, not the team**, and its input text says so.

Real output:

```text
KubernesDeployment  37.0  (4/5)   PIPELINE 4.5   ← the CI anomaly, visible
payments-api (demo) 63.3  (4/5)   RUNTIME 50.0   ← exactly 1 of 2 deploys clean
```

PIPELINE 4.5 sitting next to DELIVERY 59.4 is the point: the composite does not
hide a bad dimension behind good ones.

---

## 9 · Evidence (`services/evidence.py`)

The seam between deterministic logic and AI. Covered in chapter 08.

One property worth stating here: the evidence package **reconciles itself**.
The delivery trace is built from source control alone, so it marks DEPLOYMENT,
RUNTIME and INCIDENT unobserved regardless of other providers. Left uncorrected,
a package could claim runtime was not observed while simultaneously carrying a
runtime-degradation conflict.

Self-contradictory evidence must never reach a model, so those three stages are
reconciled against real data before assembly — with four tests covering it.

---

**Next:** [08 · The AI layer](08-ai-layer.md)
