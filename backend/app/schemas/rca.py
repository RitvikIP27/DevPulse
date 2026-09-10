"""Structured RCA output (PRD 3.1).

The model must return exactly this shape. Free-form prose is not accepted,
because prose is where unsupported certainty hides — a schema forces the model
to separate what it observed from what it is inferring, and to fill in
`unknowns` rather than quietly omitting them.
"""

from enum import Enum

from pydantic import BaseModel, Field


class RcaConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    #: The evidence does not support a conclusion at all.
    INSUFFICIENT = "INSUFFICIENT"


class Hypothesis(BaseModel):
    hypothesis: str = Field(description="A candidate explanation, stated plainly.")
    supporting_evidence: list[str] = Field(
        description="Facts from the evidence package that support this. Quote them."
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="Facts that argue against this hypothesis, if any.",
    )
    confidence: RcaConfidence


class RcaResult(BaseModel):
    summary: str = Field(description="What happened, in one or two sentences.")
    likely_cause: str = Field(
        description=(
            "The strongest explanation the evidence supports. Use hedged language "
            "unless the evidence is conclusive. Never assert causation from timing."
        )
    )
    confidence: RcaConfidence
    affected_stage: str | None = Field(
        default=None, description="Pipeline stage most implicated, if any."
    )
    impact: str = Field(description="What this means for users or the team.")

    observed_facts: list[str] = Field(
        description="Facts taken directly from the evidence package."
    )
    inferences: list[str] = Field(
        description="Conclusions drawn from those facts. Not facts themselves."
    )
    alternative_hypotheses: list[Hypothesis] = Field(
        description="Other explanations considered, with their evidence."
    )

    recommended_investigation: list[str] = Field(
        description="Specific next steps to narrow this down."
    )
    recommended_actions: list[str] = Field(
        description="Concrete, specific actions. Never generic advice."
    )
    unknowns: list[str] = Field(
        description="What the available evidence cannot determine."
    )


class RcaResponse(BaseModel):
    """An RCA plus how it was produced."""

    available: bool
    unavailable_reason: str | None = None

    evidence_hash: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    generated_at: str | None = None
    cached: bool = False

    result: RcaResult | None = None
    #: Claims whose cited evidence could not be found in the package.
    integrity_warnings: list[str] = []
