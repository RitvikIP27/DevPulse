# 14 · Defending the project

Questions you are likely to be asked, and honest answers.

---

## "What is DevPulse, in one sentence?"

> A platform that joins data from GitHub, CI, deployment, monitoring and incident
> systems to reconstruct how a code change reached production, measures delivery
> performance, and reports where it is slow or breaking — while explicitly
> stating what it cannot see.

---

## "What makes it more than a dashboard?"

Three things a dashboard does not do:

**1. Correlation.** It works out that a pull request, a CI run, a deployment and
an incident describe the *same change* — by commit identity, never by timing.

**2. Conflict detection.** It notices when systems disagree. ArgoCD says the
deployment succeeded; Prometheus says the error rate went up 2200%. Both are
reporting truthfully about different things, and only something joining them
catches it.

**3. Explicit ignorance.** It distinguishes "zero failures" from "no monitoring
connected". Most dashboards render both as `0`.

---

## "Why did you build it this way rather than just calling an LLM?"

Because an LLM asked to gather *and* interpret data produces fluent,
unverifiable answers. At 3am an engineer cannot tell which parts were measured
and which were generated.

DevPulse establishes every fact deterministically first, then hands the model a
structured evidence package — with no database access, no API keys, no logs. The
model interprets; it never discovers.

That is ADR-008, and it was decided *before* any AI code was written.

---

## "Show me a bug you found and fixed."

The best one is the whole reason the project has an audit document.

The original MVP counted every successful CI workflow run as a production
deployment. I ran the system against a real repository and checked the data in
SQL:

- Of **34** runs counted as deployments, only **6** were deployment-shaped — the
  rest were CI and infrastructure workflows. Deployment frequency was overstated
  roughly **5.7×**.
- Lead time was measured as "PR merge → next successful run". But merging
  triggers CI within seconds, so it always matched the CI job the merge itself
  started. Measured per PR: **0.1, 0.1, 0.0, 0.1, 0.1 minutes**. It was
  reporting webhook latency as delivery performance.

I encoded both as `xfail(strict=True)` tests asserting the *correct* behaviour,
so the suite stayed green while the defect stood — and would **fail the moment
it was fixed**, forcing acknowledgement.

When the deployment model landed, frequency moved from 2.64/wk to **0.47/wk — a
5.6× correction**, closely matching the 5.7× the audit predicted. That agreement
is the evidence the audit measured the right thing.

---

## "What is the hardest part of the codebase?"

The bottleneck scoring, because the obvious approach is wrong.

"The slowest stage is the bottleneck" ignores that a stage which has *always*
taken twenty minutes is a cost, not a constraint. The stage that used to take
five and now takes forty is where delivery is being lost.

So it combines four weighted signals — latency contribution, historical
regression, failure impact, frequency — and the weights **renormalise** when a
signal is unavailable. Scoring a missing baseline as zero would penalise a stage
for the accident of having no history.

Every score decomposes into its components with an explaining sentence each,
because a number nobody can take apart gets argued with rather than acted on.

---

## "Why median instead of average?"

Because delivery data is heavily skewed. On the audited repository CI has a
**median of 4.2 minutes and a p90 of 609 minutes** — one run queued over a
weekend. A mean describes neither: it is far above typical and far below the
outlier.

The codebase also uses **MAD** (median absolute deviation) rather than standard
deviation, for the same reason — it is itself a median, so one outlier cannot
inflate it.

---

## "How do you know your metrics are correct?"

Three ways:

1. **Ground-truth tests.** The PRD's worked example — merged at 10:00, deployed
   at 11:15, lead time 75 minutes — is asserted directly in the test suite.
2. **Negative tests.** Most valuable tests assert what must *not* happen: a run
   with a different commit is never attached, an improvement is never an anomaly,
   a dimension with no data never scores zero.
3. **Cross-checks.** The bottleneck engine and the anomaly engine share one
   statistics module, so both independently report the same +253.8% CI
   regression. If they disagreed, one would be wrong.

---

## "What would you do differently?"

**Capture the commit SHA from day one.** The MVP stored no commit identifier
anywhere, which meant correlation — the product's core capability — was
impossible until a migration added it. Every downstream feature was blocked on a
column that costs nothing to add.

**Write the audit first.** I built on assumptions for a while before measuring.
The audit took a few hours and invalidated several of them.

---

## "What is not finished?"

Honestly:

- **No end-to-end tests.** Playwright is planned, not built.
- **No rate limiting** on login.
- **No roles or multi-user management** — one owner account, no invites.
- **Runtime and incident connectors are untested against real instances.** The
  code is written and unit-tested; I have no Prometheus or PagerDuty, so the
  synthetic scenarios are what demonstrate it.
- **Unit tests run on SQLite**, not PostgreSQL. Migrations are verified against
  real PostgreSQL in CI, but anything PostgreSQL-specific lacks an integration
  test.
- **Rework rate is a lower bound**, and the UI says so — remediation not
  preceded by an observed deployment failure is invisible without incident data.

---

## "Why so many documents?"

Because decisions outlive the reasoning behind them. Six months on, nobody
remembers why bottleneck weights are 0.40/0.25/0.20/0.15 — and without the
reason, the next person either treats them as sacred or changes them blindly.

`Decision.md` holds 28 ADRs, each with context, decision, and why alternatives
were rejected.

---

## "Walk me through the code."

Suggested order — each step builds on the last:

```text
1. models/events.py        what exists (12 tables)
2. services/timestamps.py  smallest real file; explains the tz bug
3. services/baselines.py   pure statistics, no database
4. services/deliveries.py  correlation — the heart of it
5. services/bottlenecks.py how a score is built and explained
6. services/conflicts.py   the differentiating feature
7. services/evidence.py    the AI boundary
8. main.py                 how it is wired, and router-level auth
```

---

## "Demo it in 60 seconds."

```bash
cd ~/DevPulse/DevPulse && docker compose up -d
docker compose exec backend python -m app.demo_seed
```

Then, at http://localhost:5173 — **select Last 90 days first**:

1. **Settings** → add deployment rule `CD Workflow` → DORA goes from `—` to five
   real metrics. *"That is 2.64/wk becoming 0.47/wk — the 5.6× correction."*
2. **Health** → `Control plane: SUCCESS` next to `Runtime: Degraded`. *"Both
   systems are telling the truth. Only something joining them catches this."*
3. **Deliveries** → PR #27 → *"Ten runs correlated on commit identity, not
   timing — and it says so."*
4. **Switch to Last 30 days** → everything reads `—`. *"Never `0.0%`. That is the
   whole product in one interaction."*

---

## The one thing to remember

If you only retain one sentence:

> **Missing data is reported as missing, never as zero.**

Every architectural decision follows from taking that seriously — nullable
columns, `unavailable_reason` strings, the `NOT_CONFIGURED` enum value, weights
that renormalise, health dimensions that score `null`, and a conflict vocabulary
with no word for "caused".

It came from a real bug: an empty repository ranked as the **healthiest service**
because absent data scored as a perfect record.

---

**Back to:** [the index](README.md)
