"""Assembles the evidence package (PRD 3.1, Stage 15).

This is the seam between the deterministic core and AI. Everything the AI layer
will ever see is built here, from engines that have already been tested in
isolation. Nothing in this module calls a model.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.models.events import Deployment, PullRequest, Repository
from app.schemas.evidence import (
    EvidenceCoverage,
    EvidenceIncident,
    EvidencePackage,
    EvidenceStage,
)
from app.schemas.deliveries import StageStatus
from app.schemas.repositories import PipelineStage
from app.services.bottlenecks import detect_bottlenecks
from app.services.conflicts import (
    INCIDENT_ASSOCIATION_MINUTES,
    _detect,
    _incidents_after,
    compare_runtime_around,
)
from app.services.deliveries import _build_stages, _runs_for
from app.services.repositories import list_repositories
from app.services.timestamps import utc_now


def _fingerprint(payload: dict) -> str:
    """Stable hash of the facts, ignoring generation time.

    Sorted keys so an identical set of facts always produces an identical hash
    regardless of dictionary ordering — otherwise caching would never hit.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def build_evidence(db: Session, deployment_id: int) -> EvidencePackage | None:
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if deployment is None:
        return None

    repo = db.query(Repository).filter(Repository.id == deployment.repository_id).first()
    if repo is None:
        return None

    anchor = deployment.finished_at or deployment.started_at

    # The change this deployment shipped, matched by commit rather than by time.
    pr = None
    if deployment.commit_sha:
        pr = (
            db.query(PullRequest)
            .filter(PullRequest.repository_id == repo.id)
            .filter(PullRequest.merge_commit_sha == deployment.commit_sha)
            .first()
        )

    runtime = compare_runtime_around(db, deployment)
    incident_rows = _incidents_after(db, deployment)
    conflicts = _detect(deployment, runtime, incident_rows)

    # The delivery trace is built from source-control data alone, so it marks
    # DEPLOYMENT, RUNTIME and INCIDENT as unobserved regardless of what other
    # providers reported. Left uncorrected, the package would state that runtime
    # was not observed while also carrying a runtime-degradation conflict — and
    # self-contradictory evidence is precisely what must never reach a model.
    deployment_observations = {
        PipelineStage.DEPLOYMENT: (
            deployment.status,
            f"Deployment to {deployment.environment} reported {deployment.status}.",
        ),
        PipelineStage.RUNTIME: (
            (
                StageStatus.FAILED.value
                if any(shift.is_degradation for shift in runtime.shifts)
                else StageStatus.SUCCESS.value
            )
            if runtime.available
            else StageStatus.NOT_OBSERVED.value,
            (
                f"Runtime compared across {runtime.window_minutes} minutes either side."
                if runtime.available
                else (runtime.unavailable_reason or "Runtime not observed.")
            ),
        ),
        PipelineStage.INCIDENT: (
            StageStatus.FAILED.value if incident_rows else StageStatus.NOT_OBSERVED.value,
            (
                f"{len(incident_rows)} incident(s) opened shortly after this deployment."
                if incident_rows
                else "No incident associated with this deployment."
            ),
        ),
    }

    stages: list[EvidenceStage] = []
    if pr is not None:
        for stage in _build_stages(pr, _runs_for(db, repo.id, deployment.commit_sha or "")):
            override = deployment_observations.get(stage.stage)
            stages.append(
                EvidenceStage(
                    stage=stage.stage,
                    status=override[0] if override else stage.status.value,
                    duration_minutes=stage.duration_minutes,
                    detail=override[1] if override else stage.detail,
                )
            )

    incidents = [
        EvidenceIncident(
            title=incident.title,
            status=incident.status,
            started_at=incident.started_at,
            resolved_at=incident.resolved_at,
            minutes_after_deployment=round(
                (incident.started_at - anchor).total_seconds() / 60.0, 1
            ),
        )
        for incident in incident_rows
    ]

    bottlenecks = detect_bottlenecks(db, repository_id=repo.id, window_days=30).stages

    summary = next(
        (
            summary
            for summary in list_repositories(db).repositories
            if summary.id == repo.id
        ),
        None,
    )
    observed = [s.stage for s in stages if s.status != StageStatus.NOT_OBSERVED.value]
    unobserved = [s.stage for s in stages if s.status == StageStatus.NOT_OBSERVED.value]

    known_limitations: list[str] = []
    if not runtime.available:
        known_limitations.append(
            runtime.unavailable_reason
            or "Runtime health around this deployment is unknown."
        )
    if not incident_rows:
        known_limitations.append(
            f"No incident opened within {INCIDENT_ASSOCIATION_MINUTES} minutes of this "
            "deployment, but that only rules out incidents DevPulse can see."
        )
    if pr is None:
        known_limitations.append(
            "No merged pull request could be matched to this deployment's commit, so "
            "the change it shipped is unknown."
        )
    known_limitations.append(
        "Stage timings measure elapsed time, not effort. Review duration is the "
        "interval a pull request stayed open, not time spent reviewing."
    )

    facts = {
        "repository": repo.full_name,
        "deployment_id": deployment.id,
        "environment": deployment.environment,
        "commit_sha": deployment.commit_sha,
        "deployment_status": deployment.status,
        "deployed_at": anchor,
        "stages": [s.model_dump() for s in stages],
        "runtime": runtime.model_dump(),
        "incidents": [i.model_dump() for i in incidents],
        "conflicts": [c.model_dump() for c in conflicts],
        "bottlenecks": [b.model_dump() for b in bottlenecks],
    }

    return EvidencePackage(
        evidence_hash=_fingerprint(facts),
        generated_at=utc_now(),
        repository_full_name=repo.full_name,
        service=repo.display_name or repo.full_name,
        deployment_id=deployment.id,
        environment=deployment.environment,
        commit_sha=deployment.commit_sha,
        deployment_status=deployment.status,
        deployed_at=anchor,
        pull_request_number=pr.github_pr_number if pr else None,
        pull_request_title=pr.title if pr else None,
        author_login=pr.author_login if pr else None,
        stages=stages,
        bottlenecks=bottlenecks,
        runtime=runtime,
        incidents=incidents,
        conflicts=conflicts,
        coverage=EvidenceCoverage(
            confidence=summary.coverage.confidence if summary else "MINIMAL",
            confidence_reason=summary.coverage.confidence_reason if summary else "Unknown.",
            observed_stages=observed,
            unobserved_stages=unobserved,
        ),
        known_limitations=known_limitations,
    )
