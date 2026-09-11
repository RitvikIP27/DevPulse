# 02 · The problem DevPulse solves

## The scattered-evidence problem

A single change to a payments service touches many systems. Each one keeps a
fragment of the story, and none of them keep the whole thing:

```text
  GitHub            "PR #482 was merged at 14:32, commit abc123"
  GitHub Actions    "run #18291 on commit abc123 succeeded at 14:41"
  ArgoCD            "revision abc123 deployed to production at 14:48"
  Kubernetes        "rollout of payments:abc123 completed"
  Prometheus        "error rate went from 0.8% to 18.4% at 14:52"
  PagerDuty         "incident #921 opened at 14:54"
```

Every one of those systems will tell you it succeeded. GitHub says the PR
merged. Actions says CI passed. ArgoCD says the deployment succeeded. Kubernetes
says the rollout completed.

**And production is on fire.**

No single tool is lying. Each is answering a narrower question than the one that
matters. ArgoCD knows its own rollout mechanism finished; it knows nothing about
whether the application still works.

## The question nobody can answer

> "This change went out at 14:48. Did it break anything, how long did it take to
> get there, and where did the time go?"

Answering that needs all six systems joined together. That join is DevPulse's
entire reason to exist.

## The joining key

Look again at the fragments. Notice what repeats:

```text
  PR #482            commit abc123
  run #18291         commit abc123
  ArgoCD revision    commit abc123
  Kubernetes image   payments:abc123
```

The **commit SHA** is the thread running through all of them. A commit SHA is a
40-character fingerprint of a specific set of code changes — globally unique,
and carried by every system that touches that code.

So DevPulse correlates on commit identity. That is the whole trick.

### Why not just use time?

The tempting shortcut is "the deployment closest in time to the merge". DevPulse
explicitly refuses to do this, and the reason is not theoretical — the original
MVP did exactly that and produced nonsense.

Merging a PR triggers CI within *seconds*. So "the next successful run after a
merge" is always the CI job the merge itself started, never the deployment. Lead
time measured that way came out as **0.1 minutes for every single pull request**.
It was measuring webhook latency and calling it delivery performance.

The audit that caught this is [`docs/architecture-audit.md`](../architecture-audit.md).
The rule that came out of it lives in `rules.md` §9:

> Never use time proximity as the only proof of identity.

## What DevPulse builds from the join

Once records are joined by commit, you can reconstruct the change's whole
journey — a **delivery trace**:

```text
Delivery · PR #482                                   commit abc123

  SOURCE      ●  Commit abc123 on main
  REVIEW      ●  Open for review                          5h 20m
  CI          ●  3 workflow runs reported this commit         8m
  QUALITY     ○  No code-quality integration connected
  BUILD       ○  Build events not distinguished from CI
  ARTIFACT    ○  No artifact registry connected
  DEPLOYMENT  ●  Deployed to production                       3m
  ROLLOUT     ○  No orchestrator connected
  RUNTIME     ●  Error rate 0.8% → 18.4%              ← DEGRADED
  INCIDENT    ●  1 incident opened 4 minutes later
```

Filled circles are observed. Hollow circles are **honestly unobserved** — no
connector provides them. That distinction is the product.

From traces you can derive everything else:

- **How long each stage took** → bottlenecks
- **How that compares to last month** → baselines and anomalies
- **How often changes reach production and how often they break** → DORA metrics
- **Whether the deployment platform and monitoring agree** → conflict detection

## The honesty problem

Here is the trap that catches most dashboards.

If DevPulse has no monitoring connected, what should the RUNTIME row say?

The easy answer is to show `0 errors` — the query returned nothing, so zero.
That is **catastrophically wrong**. It tells the reader production is healthy
when the truth is *DevPulse has no idea*.

The audit found this exact bug: a repository with no data at all was ranked the
**best-performing service**, because its change-failure rate computed to `0.0%`.

So DevPulse keeps three states rigidly apart, everywhere:

| State | Meaning |
|---|---|
| A number | We measured it. This is the value. |
| **Unavailable** | We are watching, but cannot compute this from what we have. |
| **Not observed / Not configured** | We are not watching at all. |

You will see this distinction in the database (`nullable` columns), in the API
(`null` plus an `unavailable_reason` string), and in the UI (`—` and "Not
observed" badges, never `0`).

## Where AI fits

AI is deliberately last, and deliberately small.

The temptation is to point a language model at the raw APIs and ask "what
happened?". That produces confident, fluent, unverifiable answers — the exact
opposite of what an engineering team needs at 3am.

Instead the deterministic pipeline establishes every fact first, packages them,
and hands the model that package and **nothing else**. No database access, no
logs, no API keys. The model's job is interpretation, not discovery.

This is recorded as ADR-008 in [`Decision.md`](../../Decision.md) and enforced by
the architecture: the AI code physically cannot reach the database.

---

**Next:** [03 · Python and FastAPI](03-python-and-fastapi.md)
