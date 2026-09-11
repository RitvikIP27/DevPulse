# 08 · The AI layer

## The temptation, and why DevPulse refuses it

The obvious way to add AI to a DevOps tool:

```text
   "What went wrong?"  ──►  LLM  ──►  calls GitHub, Prometheus, PagerDuty
                                 ──►  "The deployment caused a 34% latency spike
                                       in the payment service due to a memory
                                       leak in the connection pool."
```

That answer is fluent, specific, actionable — and **possibly entirely invented**.
The model had to gather data, interpret it, and narrate it in one step, with
nothing checking the middle. At 3am, an engineer cannot tell which parts were
measured and which were generated.

DevPulse inverts it:

```text
  connectors ──► correlation ──► metrics ──► baselines ──► conflicts
                                      │
                                      ▼
                            EVIDENCE PACKAGE  (deterministic, testable)
                                      │
                                      ▼
                                    LLM  ──►  structured interpretation
```

The facts are established before the model is called. The model interprets; it
never discovers. This is **ADR-008**, decided before any AI code was written —
AI was deliberately deferred until the deterministic pipeline was complete.

## The evidence package

`services/evidence.py` assembles one object per deployment from engines that
were each built and tested in isolation:

```python
class EvidencePackage(BaseModel):
    evidence_hash: str
    repository_full_name: str
    deployment_status: str
    commit_sha: str | None

    stages: list[EvidenceStage]        # from the delivery trace
    bottlenecks: list[StageAnalysis]   # from the bottleneck engine
    runtime: RuntimeComparison         # before/after the deployment
    incidents: list[EvidenceIncident]
    conflicts: list[Conflict]
    coverage: EvidenceCoverage

    known_limitations: list[str]
```

**The model receives this serialised, and nothing else.** No database session,
no API keys, no log access. It physically cannot fetch anything.

### `known_limitations` is the unusual field

The package tells the model what it *cannot* answer:

> "No monitoring provider is connected, so DevPulse cannot determine whether this
> deployment affected production health."
>
> "Stage timings measure elapsed time, not effort. Review duration is the
> interval a pull request stayed open, not time spent reviewing."

A model given incomplete data tends to work *around* the gap. A model *told* about
the gap reports it. Carrying limitations into the prompt is the difference.

### `evidence_hash`

A SHA-256 fingerprint of the facts, excluding generation time:

```python
canonical = json.dumps(payload, sort_keys=True, default=str)
return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

`sort_keys=True` matters — without it, dictionary ordering would change the hash
for identical facts and caching would never hit.

The hash does two jobs: identical facts reuse a stored analysis rather than being
paid for again, and any stored analysis is traceable to the exact facts that
produced it.

## The provider abstraction

`services/ai/provider.py`:

```python
class AIProvider(Protocol):
    name: str
    model: str
    def is_configured(self) -> bool: ...
    def generate_rca(self, evidence: EvidencePackage, prompt: str) -> RcaResult: ...
```

A **Protocol** means "anything with these methods will do" — no inheritance
required. Nothing outside `services/ai/` imports the Anthropic SDK, so swapping
vendors means adding one file.

The tests use a `FakeProvider`. **No test calls a real model:** that would be
slow, cost money, and make the suite non-deterministic. What is under test is
DevPulse's handling of model output, not the model.

## The three guards (ADR-024)

### Guard 1 — structured output

The model must return the `RcaResult` schema:

```python
class RcaResult(BaseModel):
    summary: str
    likely_cause: str
    confidence: RcaConfidence           # HIGH / MEDIUM / LOW / INSUFFICIENT
    observed_facts: list[str]           # traceable to the evidence
    inferences: list[str]               # reasoning about them, kept separate
    alternative_hypotheses: list[Hypothesis]
    recommended_investigation: list[str]
    recommended_actions: list[str]
    unknowns: list[str]                 # required, not optional
```

Prose is where unsupported certainty hides. A schema forces the model to commit
to which category each statement belongs in — and `INSUFFICIENT` exists so
"the evidence does not support a conclusion" is a **valid answer** rather than
something the model must talk its way around.

The system prompt (`services/ai/prompts.py`, versioned as `rca-v1`) states the
rules explicitly, including:

> Never assert that one thing caused another because it happened first.
> Temporal proximity is evidence, not proof.

and

> If the evidence does not support a conclusion, set confidence to INSUFFICIENT
> and say so plainly. That is a correct and useful answer. Do not manufacture a
> plausible story to fill the space.

### Guard 2 — integrity checking

```python
def check_integrity(result: RcaResult, evidence: EvidencePackage) -> list[str]:
    evidence_numbers = _numbers_in(evidence.model_dump_json())
    for claim in result.observed_facts + [result.likely_cause, result.summary]:
        unsupported = _numbers_in(claim) - evidence_numbers
        if unsupported:
            warnings.append(f'"{claim[:90]}" cites {unsupported}, '
                            "which does not appear in the evidence package.")
```

Numbers in the model's output are checked against the evidence text. Anything
unsupported is surfaced **beside** the analysis as a warning.

**Be honest about what this does and does not do.** It cannot prove an analysis
sound. It catches one specific failure — a confident-looking figure the model
*wrote* rather than *read*. Small integers are excluded because they appear in
ordinary prose ("two stages") and would produce constant false warnings.

It warns; it does not block. The reader is informed, not gated.

There is a test worth knowing about. The evidence package stores the **median**
of runtime samples, not the raw readings. A test initially asserted a model
quoting a raw sample (`18.4`) would pass the check — it did not, because `18.4`
genuinely was not in the package; only the median `18.2` was. The guard was
correct and the test was wrong. That is the guard doing its job.

### Guard 3 — caching and provenance

```python
record = RcaAnalysis(
    evidence_hash=evidence.evidence_hash,
    provider=provider.name,
    model=provider.model,
    prompt_version=PROMPT_VERSION,
    result_json=result.model_dump_json(),
    evidence_json=evidence.model_dump_json(),
    created_at=utc_now(),
)
```

Every analysis is stored with the **evidence, model and prompt version** that
produced it. That makes it reproducible, and makes the same facts free to
re-read.

## Degradation without a key

With no provider configured, the RCA endpoint returns:

```json
{
  "available": false,
  "evidence_hash": "cd52ffb1cbd059d3",
  "unavailable_reason": "No AI provider is configured... The evidence package
    below is complete and was produced deterministically — it is the basis any
    analysis would have used. Set ANTHROPIC_API_KEY to enable reasoning over it."
}
```

**The evidence package is still built and returned.** The deterministic layer is
the product; AI is an interpretation of it, and its absence must not hide the
facts.

The SDK import is inside the method for the same reason: a missing optional
dependency must never be able to take down the deterministic core.

## Cost control

Analysis is not run automatically on everything. `GET /api/analysis/candidates`
ranks deployments **conflicts-first**, because analysis costs money and the
deployments where systems disagree are where it pays off. Running it is an
explicit `POST`, and identical evidence returns the cached result.

## The model configuration

```python
response = client.messages.parse(
    model="claude-opus-5",
    max_tokens=16000,
    system=SYSTEM_PROMPT,
    thinking={"type": "adaptive"},
    messages=[{"role": "user", "content": build_user_prompt(prompt)}],
    output_format=RcaResult,
)
```

- `thinking={"type": "adaptive"}` — the model reasons before answering, which
  suits weighing conflicting signals.
- `output_format=RcaResult` — structured output, validated into the Pydantic
  model automatically.
- A safety refusal returns HTTP 200 with `stop_reason: "refusal"`, so the status
  code alone is not enough; that case is checked explicitly.

---

**Next:** [09 · React and the frontend](09-react-frontend.md)
