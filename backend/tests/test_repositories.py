"""Repository listing and data-coverage tests.

Coverage is the mechanism that stops DevPulse presenting absent telemetry as
healthy telemetry, so its edges matter more than its happy path.
"""

from app.schemas.repositories import (
    AnalysisConfidence,
    CoverageStatus,
    PipelineStage,
)
from app.services.repositories import list_repositories


def _stage(coverage, stage: PipelineStage):
    return next(entry for entry in coverage.stages if entry.stage is stage)


def test_no_repositories_returns_an_empty_list(db_session):
    assert list_repositories(db_session).repositories == []


def test_ingested_activity_is_counted_per_repository(db_session, repository, runs):
    runs.add(started_minutes_ago=60)
    runs.add(started_minutes_ago=30)
    runs.add_merged_pr(number=1, merged_minutes_ago=90)

    summary = list_repositories(db_session).repositories[0]

    assert summary.full_name == "devpulse-test/payments-api"
    assert summary.workflow_run_count == 2
    assert summary.pull_request_count == 1
    assert summary.last_activity_at is not None


def test_connected_stages_with_data_report_available(db_session, repository, runs):
    runs.add(started_minutes_ago=60)
    runs.add_merged_pr(number=1, merged_minutes_ago=90)

    coverage = list_repositories(db_session).repositories[0].coverage

    assert _stage(coverage, PipelineStage.SOURCE).status is CoverageStatus.AVAILABLE
    assert _stage(coverage, PipelineStage.CI).status is CoverageStatus.AVAILABLE


def test_a_connected_stage_with_nothing_ingested_is_no_data_not_unconfigured(
    db_session, repository
):
    """DevPulse is watching and has seen nothing. That is not the same as not watching."""
    coverage = list_repositories(db_session).repositories[0].coverage

    assert _stage(coverage, PipelineStage.CI).status is CoverageStatus.NO_DATA
    assert _stage(coverage, PipelineStage.CI).record_count == 0


def test_stages_without_an_integration_are_not_configured(db_session, repository, runs):
    runs.add(started_minutes_ago=60)

    coverage = list_repositories(db_session).repositories[0].coverage

    for stage in (
        PipelineStage.DEPLOYMENT,
        PipelineStage.RUNTIME,
        PipelineStage.INCIDENT,
        PipelineStage.QUALITY,
        PipelineStage.ARTIFACT,
    ):
        assert _stage(coverage, stage).status is CoverageStatus.NOT_CONFIGURED


def test_deployment_and_runtime_gaps_are_explained_not_merely_flagged(
    db_session, repository, runs
):
    runs.add(started_minutes_ago=60)

    coverage = list_repositories(db_session).repositories[0].coverage

    assert "not production measurements" in _stage(coverage, PipelineStage.DEPLOYMENT).detail
    assert "degraded production" in _stage(coverage, PipelineStage.RUNTIME).detail


def test_missing_deployment_and_runtime_reduce_confidence_below_high(
    db_session, repository, runs
):
    runs.add(started_minutes_ago=60)
    runs.add_merged_pr(number=1, merged_minutes_ago=90)

    coverage = list_repositories(db_session).repositories[0].coverage

    # Source and CI are visible; deployment and runtime are not.
    assert coverage.confidence is AnalysisConfidence.LIMITED
    assert "2 of 4" in coverage.confidence_reason
    assert "DEPLOYMENT" in coverage.confidence_reason
    assert "RUNTIME" in coverage.confidence_reason


def test_a_repository_with_no_data_at_all_has_minimal_confidence(db_session, repository):
    coverage = list_repositories(db_session).repositories[0].coverage

    assert coverage.confidence is AnalysisConfidence.MINIMAL


def test_repositories_endpoint_exposes_coverage(api_client, repository, runs):
    runs.add(started_minutes_ago=60)
    runs.add_merged_pr(number=1, merged_minutes_ago=90)

    response = api_client.get("/api/repositories")

    assert response.status_code == 200
    body = response.json()["repositories"]
    assert len(body) == 1
    assert body[0]["full_name"] == "devpulse-test/payments-api"
    assert body[0]["coverage"]["confidence"] == "LIMITED"
    assert len(body[0]["coverage"]["stages"]) == len(PipelineStage)
