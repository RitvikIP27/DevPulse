"""Delivery trace reconstruction tests.

Correlation correctness is the point: a trace that attaches the wrong records to
a change is worse than no trace at all.
"""

from app.schemas.deliveries import CorrelationMethod, StageStatus
from app.schemas.repositories import PipelineStage
from app.services.deliveries import get_delivery, list_deliveries

MERGE_SHA = "abc123def456"
OTHER_SHA = "xyz999zzz111"


def _merged_pr(runs_builder, session, repository, *, number=482, sha=MERGE_SHA, merged_minutes_ago=60.0):
    pr = runs_builder.add_merged_pr(number=number, merged_minutes_ago=merged_minutes_ago, opened_minutes_ago=360.0)
    pr.merge_commit_sha = sha
    pr.base_branch = "main"
    pr.author_login = "octocat"
    session.commit()
    return pr


def _stage(delivery, stage: PipelineStage):
    return next(s for s in delivery.stages if s.stage is stage)


def test_runs_sharing_the_merge_commit_are_attached_to_the_delivery(db_session, repository, runs):
    _merged_pr(runs, db_session, repository)
    run = runs.add(workflow_name="CI", conclusion="success", started_minutes_ago=59)
    run.head_sha = MERGE_SHA
    db_session.commit()

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert delivery is not None
    ci = _stage(delivery, PipelineStage.CI)
    assert ci.status is StageStatus.SUCCESS
    assert len(ci.runs) == 1


def test_a_run_with_a_different_commit_is_never_attached(db_session, repository, runs):
    """Correlation must not fall back to timestamp proximity (rules.md 9).

    This run happens seconds after the merge, which is exactly the situation the
    broken lead-time metric was fooled by.
    """
    _merged_pr(runs, db_session, repository)
    unrelated = runs.add(workflow_name="Unrelated CI", conclusion="success", started_minutes_ago=59.9)
    unrelated.head_sha = OTHER_SHA
    db_session.commit()

    delivery = get_delivery(db_session, f"{repository.id}-482")

    ci = _stage(delivery, PipelineStage.CI)
    assert ci.status is StageStatus.NOT_OBSERVED
    assert ci.runs == []


def test_review_duration_is_measured_from_open_to_merge(db_session, repository, runs):
    # Opened 360 minutes ago, merged 60 minutes ago -> 300 minutes of review.
    _merged_pr(runs, db_session, repository)

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert _stage(delivery, PipelineStage.REVIEW).duration_minutes == 300.0


def test_a_failed_run_makes_the_delivery_failed(db_session, repository, runs):
    _merged_pr(runs, db_session, repository)
    failed = runs.add(workflow_name="CI", conclusion="failure", started_minutes_ago=59)
    failed.head_sha = MERGE_SHA
    db_session.commit()

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert _stage(delivery, PipelineStage.CI).status is StageStatus.FAILED
    assert delivery.status is StageStatus.FAILED


def test_unobserved_stages_do_not_make_a_delivery_look_failed(db_session, repository, runs):
    """Absence of evidence is not evidence of failure (ADR-011)."""
    _merged_pr(runs, db_session, repository)
    run = runs.add(conclusion="success", started_minutes_ago=59)
    run.head_sha = MERGE_SHA
    db_session.commit()

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert delivery.status is StageStatus.SUCCESS
    assert _stage(delivery, PipelineStage.DEPLOYMENT).status is StageStatus.NOT_OBSERVED
    assert _stage(delivery, PipelineStage.RUNTIME).status is StageStatus.NOT_OBSERVED


def test_deployment_gap_is_explained_rather_than_left_blank(db_session, repository, runs):
    _merged_pr(runs, db_session, repository)

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert "cannot confirm this change reached production" in _stage(
        delivery, PipelineStage.DEPLOYMENT
    ).detail


def test_correlation_records_its_basis(db_session, repository, runs):
    _merged_pr(runs, db_session, repository)
    run = runs.add(conclusion="success", started_minutes_ago=59)
    run.head_sha = MERGE_SHA
    db_session.commit()

    delivery = get_delivery(db_session, f"{repository.id}-482")

    assert delivery.correlation.method is CorrelationMethod.COMMIT_SHA
    assert "not\ntimestamp proximity" in delivery.correlation.evidence.replace(" ", " ") or \
           "not timestamp proximity" in delivery.correlation.evidence
    assert delivery.correlation.commit_sha == MERGE_SHA


def test_a_merged_pr_without_a_merge_commit_is_reported_not_dropped(db_session, repository, runs):
    """Ingested before correlation keys existed; it has no join key."""
    runs.add_merged_pr(number=100, merged_minutes_ago=120)  # no merge_commit_sha
    _merged_pr(runs, db_session, repository)

    response = list_deliveries(db_session)

    assert response.uncorrelatable_count == 1
    assert len(response.deliveries) == 1


def test_unmerged_pull_requests_are_not_deliveries(db_session, repository, runs):
    response = list_deliveries(db_session)
    assert response.deliveries == []


def test_delivery_endpoint_returns_a_trace(api_client, db_session, repository, runs):
    _merged_pr(runs, db_session, repository)
    run = runs.add(conclusion="success", started_minutes_ago=59)
    run.head_sha = MERGE_SHA
    db_session.commit()

    listing = api_client.get("/api/deliveries")
    assert listing.status_code == 200
    assert len(listing.json()["deliveries"]) == 1

    detail = api_client.get(f"/api/deliveries/{repository.id}-482")
    assert detail.status_code == 200
    assert detail.json()["correlation"]["confidence"] == "HIGH"


def test_unknown_delivery_returns_404(api_client):
    assert api_client.get("/api/deliveries/9-999").status_code == 404
    assert api_client.get("/api/deliveries/not-an-id").status_code == 404
