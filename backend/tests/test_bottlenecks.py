"""Deterministic bottleneck detection (PRD 2.9).

The validation scenario from PRD section 5 is asserted directly: given review
312m, CI 8m, build 2m and deploy 3m, review must be identified as the dominant
bottleneck, and the evidence must be inspectable.
"""

from datetime import timedelta

import pytest

from app.schemas.repositories import PipelineStage
from app.services.bottlenecks import (
    MIN_DELIVERIES_FOR_ANALYSIS,
    detect_bottlenecks,
)
from tests.conftest import NOW


def _delivery(db, repository, runs, *, number, review_minutes, ci_minutes,
              merged_days_ago=2.0, ci_conclusion="success"):
    """A merged pull request plus the CI run correlated to it by commit."""
    merged_minutes_ago = merged_days_ago * 24 * 60
    pr = runs.add_merged_pr(
        number=number,
        merged_minutes_ago=merged_minutes_ago,
        opened_minutes_ago=merged_minutes_ago + review_minutes,
    )
    sha = f"sha{number}"
    pr.merge_commit_sha = sha
    db.commit()

    run = runs.add(
        workflow_name="CI",
        conclusion=ci_conclusion,
        started_minutes_ago=merged_minutes_ago,
        duration_minutes=ci_minutes,
    )
    run.head_sha = sha
    db.commit()
    return pr


def _stage(response, stage: PipelineStage):
    return next(s for s in response.stages if s.stage is stage)


class TestInsufficientData:
    def test_declines_to_conclude_from_too_few_deliveries(self, db_session, repository, runs):
        _delivery(db_session, repository, runs, number=1, review_minutes=300, ci_minutes=8)

        response = detect_bottlenecks(db_session, window_days=30)

        assert response.primary_bottleneck is None
        assert str(MIN_DELIVERIES_FOR_ANALYSIS) in response.unavailable_reason
        assert "anecdote" in response.unavailable_reason

    def test_reports_how_many_deliveries_it_saw(self, db_session, repository, runs):
        _delivery(db_session, repository, runs, number=1, review_minutes=10, ci_minutes=5)

        assert detect_bottlenecks(db_session, window_days=30).deliveries_analysed == 1


class TestPrdValidationScenario:
    """PRD section 5: review 312m dominating CI 8m must surface review."""

    @pytest.fixture
    def review_dominated(self, db_session, repository, runs):
        for number in range(1, 6):
            _delivery(db_session, repository, runs, number=number,
                      review_minutes=312, ci_minutes=8, merged_days_ago=2 + number * 0.1)
        return detect_bottlenecks(db_session, window_days=30)

    def test_identifies_review_as_the_primary_bottleneck(self, review_dominated):
        assert review_dominated.primary_bottleneck.stage is PipelineStage.REVIEW

    def test_review_dominates_the_latency_contribution(self, review_dominated):
        review = _stage(review_dominated, PipelineStage.REVIEW)
        # 312 of every 320 minutes is review.
        assert review.latency_contribution_pct == pytest.approx(97.5, abs=0.5)

    def test_the_score_is_decomposable_into_its_components(self, review_dominated):
        """PRD constraint 9: a score no one can decompose is not evidence."""
        review = _stage(review_dominated, PipelineStage.REVIEW)

        assert review.components
        assert sum(c.contribution for c in review.components) == pytest.approx(review.score, abs=0.2)
        assert sum(c.weight for c in review.components) == pytest.approx(1.0, abs=0.01)
        for component in review.components:
            assert component.explanation

    def test_evidence_is_stated_in_plain_terms(self, review_dominated):
        review = _stage(review_dominated, PipelineStage.REVIEW)
        assert any("Median duration" in item for item in review.evidence)
        assert any("% of measured delivery time" in item for item in review.evidence)


class TestScoringBehaviour:
    def test_the_slowest_stage_is_not_automatically_the_bottleneck(self, db_session, repository, runs):
        """A stage that is slow, stable and reliable is a cost, not a constraint.

        Here CI is slower in absolute terms but fails constantly, while review is
        quick and clean — the failing stage must be able to outrank on signals
        other than raw duration.
        """
        for number in range(1, 7):
            _delivery(db_session, repository, runs, number=number, review_minutes=5,
                      ci_minutes=40, merged_days_ago=2 + number * 0.1,
                      ci_conclusion="failure")

        response = detect_bottlenecks(db_session, window_days=30)
        ci = _stage(response, PipelineStage.CI)

        assert ci.failure_rate_pct == 100.0
        assert ci.impact == "HIGH"

    def test_weights_are_renormalised_when_no_baseline_exists(self, db_session, repository, runs):
        """A stage must not be penalised merely for lacking history."""
        for number in range(1, 5):
            _delivery(db_session, repository, runs, number=number, review_minutes=100,
                      ci_minutes=10, merged_days_ago=2 + number * 0.1)

        response = detect_bottlenecks(db_session, window_days=30)
        review = _stage(response, PipelineStage.REVIEW)

        assert review.change_pct is None
        assert sum(c.weight for c in review.components) == pytest.approx(1.0, abs=0.01)
        assert not any(c.name == "Historical regression" for c in review.components)
        assert any("No historical comparison" in item for item in review.evidence)

    def test_a_regression_against_the_previous_period_is_detected(self, db_session, repository, runs):
        # Baseline period: fast reviews, 31-45 days ago.
        for number in range(1, 7):
            _delivery(db_session, repository, runs, number=number, review_minutes=20,
                      ci_minutes=8, merged_days_ago=35 + number * 0.1)
        # Current period: much slower reviews.
        for number in range(10, 16):
            _delivery(db_session, repository, runs, number=number, review_minutes=200,
                      ci_minutes=8, merged_days_ago=2 + number * 0.1)

        response = detect_bottlenecks(db_session, window_days=30)
        review = _stage(response, PipelineStage.REVIEW)

        assert review.is_regression is True
        assert review.change_pct == pytest.approx(900.0, abs=1.0)
        assert any("slower than the previous period" in item for item in review.evidence)
        assert any(c.name == "Historical regression" for c in review.components)

    def test_stages_are_ranked_by_score(self, db_session, repository, runs):
        for number in range(1, 6):
            _delivery(db_session, repository, runs, number=number, review_minutes=312,
                      ci_minutes=8, merged_days_ago=2 + number * 0.1)

        response = detect_bottlenecks(db_session, window_days=30)
        scores = [stage.score for stage in response.stages]

        assert scores == sorted(scores, reverse=True)


def test_bottlenecks_endpoint_exposes_the_analysis(api_client, db_session, repository, runs):
    for number in range(1, 6):
        _delivery(db_session, repository, runs, number=number, review_minutes=312,
                  ci_minutes=8, merged_days_ago=2 + number * 0.1)

    response = api_client.get("/api/bottlenecks?window_days=30")

    assert response.status_code == 200
    body = response.json()
    assert body["primary_bottleneck"]["stage"] == "REVIEW"
    assert body["deliveries_analysed"] == 5
    assert len(body["primary_bottleneck"]["components"]) >= 3
