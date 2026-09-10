"""RCA orchestration (Stage 16).

Deterministic evidence in, structured analysis out, with three guards:

- The analysis is cached by evidence hash, so identical facts are never paid for
  twice and a stored analysis is always traceable to the facts behind it.
- Model output is checked against the evidence package. A claim citing a number
  that does not appear in the evidence is surfaced as an integrity warning
  rather than displayed as fact.
- With no provider configured the evidence package is still returned. The
  deterministic layer is the product; AI is an interpretation of it.
"""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.events import Deployment, RcaAnalysis
from app.schemas.evidence import EvidencePackage
from app.schemas.rca import RcaResponse, RcaResult
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.ai.prompts import PROMPT_VERSION
from app.services.ai.provider import AIProvider, AIUnavailable
from app.services.evidence import build_evidence
from app.services.timestamps import utc_now

logger = get_logger(__name__)

#: Numbers appearing in model output are checked against the evidence text.
#: Small integers are excluded: they appear in ordinary prose ("two stages")
#: and would produce constant false warnings.
_MIN_CHECKED_NUMBER = 10.0
_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def get_provider() -> AIProvider:
    return AnthropicProvider()


def _numbers_in(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER_PATTERN.findall(text):
        try:
            value = abs(float(raw))
        except ValueError:
            continue
        if value >= _MIN_CHECKED_NUMBER:
            found.add(raw.lstrip("+-"))
    return found


def check_integrity(result: RcaResult, evidence: EvidencePackage) -> list[str]:
    """Flag numeric claims that do not appear in the evidence.

    This cannot prove an analysis is sound, and it is not meant to. It catches
    the specific failure that matters most — a confident-looking figure the
    model produced rather than read — so a reader is warned instead of misled.
    """
    evidence_text = evidence.model_dump_json()
    evidence_numbers = _numbers_in(evidence_text)

    warnings: list[str] = []
    for label, claims in (
        ("observed fact", result.observed_facts),
        ("likely cause", [result.likely_cause]),
        ("summary", [result.summary]),
    ):
        for claim in claims:
            unsupported = _numbers_in(claim) - evidence_numbers
            if unsupported:
                warnings.append(
                    f'The {label} "{claim[:90]}" cites '
                    f"{', '.join(sorted(unsupported))}, which does not appear in the "
                    "evidence package."
                )
    return warnings


def _stored(db: Session, evidence_hash: str) -> RcaAnalysis | None:
    return (
        db.query(RcaAnalysis)
        .filter(RcaAnalysis.evidence_hash == evidence_hash)
        .order_by(RcaAnalysis.created_at.desc())
        .first()
    )


def generate_rca(
    db: Session, deployment_id: int, force: bool = False, provider: AIProvider | None = None
) -> RcaResponse:
    evidence = build_evidence(db, deployment_id)
    if evidence is None:
        return RcaResponse(available=False, unavailable_reason="Deployment not found.")

    provider = provider or get_provider()

    cached = None if force else _stored(db, evidence.evidence_hash)
    if cached is not None:
        return RcaResponse(
            available=True,
            evidence_hash=cached.evidence_hash,
            provider=cached.provider,
            model=cached.model,
            prompt_version=cached.prompt_version,
            generated_at=cached.created_at.isoformat(),
            cached=True,
            result=RcaResult.model_validate_json(cached.result_json),
        )

    if not provider.is_configured():
        return RcaResponse(
            available=False,
            evidence_hash=evidence.evidence_hash,
            unavailable_reason=(
                "No AI provider is configured, so DevPulse cannot generate a narrative "
                "analysis. The evidence package below is complete and was produced "
                "deterministically — it is the basis any analysis would have used. "
                "Set ANTHROPIC_API_KEY to enable reasoning over it."
            ),
        )

    try:
        result = provider.generate_rca(evidence, evidence.model_dump_json(indent=2))
    except AIUnavailable as error:
        logger.warning("rca unavailable deployment=%s: %s", deployment_id, error)
        return RcaResponse(
            available=False,
            evidence_hash=evidence.evidence_hash,
            unavailable_reason=str(error),
        )

    warnings = check_integrity(result, evidence)
    if warnings:
        logger.warning(
            "rca integrity warnings deployment=%s count=%d", deployment_id, len(warnings)
        )

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    record = RcaAnalysis(
        repository_id=deployment.repository_id if deployment else None,
        deployment_id=deployment_id,
        evidence_hash=evidence.evidence_hash,
        provider=provider.name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        confidence=result.confidence.value,
        result_json=result.model_dump_json(),
        evidence_json=evidence.model_dump_json(),
        created_at=utc_now(),
    )
    db.add(record)
    db.commit()

    return RcaResponse(
        available=True,
        evidence_hash=evidence.evidence_hash,
        provider=provider.name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        generated_at=record.created_at.isoformat(),
        cached=False,
        result=result,
        integrity_warnings=warnings,
    )
