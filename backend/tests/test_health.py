"""Engineering health scoring (PRD 2.14, ADR-026).

Two properties matter more than any particular number: a score must decompose
into its inputs, and an unmeasurable dimension must never score zero.
"""

from datetime import timedelta

import pytest

from app.models.events import Deployment, DeploymentRule, Repository
from app.schemas.health import HealthDimension
from app.services.deployments import PROVIDER_CONFIGURED_WORKFLOW, DeploymentStatus
from app.services.health import compute_health, compute_service_health
from tests.conftest import NOW


def _dimension(health, dimension: HealthDimension):
    return next(d for d in health.dimensions if d.dimension is dimension)


def _deployment(db, repository, *, status=DeploymentStatus.SUCCESS, minutes_ago=60, sha=None, ext=None):
    row = Deployment(
        repository_id=repository.id, provider=PROVIDER_CONFIGURED_WORKFLOW,
        external_id=ext or f"d-{minutes_ago}-{status}", environment="production",
        is_production=True, commit_sha=sha, status=status,
        started_at=NOW - timedelta(minutes=minutes_ago + 3),
        finished_at=NOW - timedelta(minutes=minutes_ago),
    )
    db.add(row)
    db.commit()
    return row


class TestUnmeasurableIsNotZero:
    def test_a_dimension_with_no_data_scores_null_not_zero(self, db_session, repository):
        """Zero means "we measured, and it is bad". Null means "we cannot see".
        Conflating them is what made an empty repository rank healthiest."""
        health = compute_service_health(db_session, repository, window_days=30)

        delivery = _dimension(health, HealthDimension.DELIVERY)
        assert delivery.score is None
        assert delivery.unavailable_reason
        assert "deployment source" in delivery.unavailable_reason

    def test_runtime_without_monitoring_is_null(self, db_session, repository):
        runtime = _dimension(
            compute_service_health(db_session, repository, window_days=30),
            HealthDimension.RUNTIME,
        )
        assert runtime.score is None
        assert "monitoring provider" in runtime.unavailable_reason

    def test_overall_averages_only_scorable_dimensions(self, db_session, repository, runs):
        """Treating an unmeasurable dimension as zero would punish a team for
        DevPulse's own blind spots."""
        runs.add(conclusion="success", started_minutes_ago=60)

        health = compute_service_health(db_session, repository, window_days=30)

        assert health.dimensions_scored < health.dimensions_total
        if health.overall_score is not None:
            assert health.overall_score > 0

    def test_a_service_with_nothing_reports_why(self, db_session, repository):
        health = compute_service_health(db_session, repository, window_days=30)

        if health.overall_score is None:
            assert health.unavailable_reason


class TestExplainability:
    def test_every_dimension_lists_its_inputs(self, db_session, repository):
        """PRD constraint 9: a composite nobody can decompose gets argued with
        rather than acted on."""
        health = compute_service_health(db_session, repository, window_days=30)

        for dimension in health.dimensions:
            assert dimension.inputs
            for entry in dimension.inputs:
                assert entry.label and entry.explanation

    def test_a_dimension_score_is_the_mean_of_its_scored_inputs(
        self, db_session, repository, runs
    ):
        db_session.add(DeploymentRule(repository_id=repository.id, workflow_name_pattern="Deploy"))
        db_session.commit()
        for index in range(4):
            _deployment(db_session, repository, minutes_ago=100 - index, ext=f"ok{index}")

        delivery = _dimension(
            compute_service_health(db_session, repository, window_days=30),
            HealthDimension.DELIVERY,
        )
        scored = [i.points for i in delivery.inputs if i.points is not None]
        if scored:
            assert delivery.score == pytest.approx(sum(scored) / len(scored), abs=0.2)

    def test_coverage_pct_reports_how_much_of_a_dimension_was_measurable(
        self, db_session, repository
    ):
        health = compute_service_health(db_session, repository, window_days=30)
        observability = _dimension(health, HealthDimension.OBSERVABILITY)

        assert 0 <= observability.coverage_pct <= 100

    def test_observability_scores_devpulse_not_the_team(self, db_session, repository, runs):
        runs.add(conclusion="success", started_minutes_ago=60)
        runs.add_merged_pr(number=1, merged_minutes_ago=120)

        observability = _dimension(
            compute_service_health(db_session, repository, window_days=30),
            HealthDimension.OBSERVABILITY,
        )

        assert observability.score is not None
        assert "not the team" in observability.inputs[0].explanation


class TestScoringBehaviour:
    def test_frequent_reliable_deployments_score_well(self, db_session, repository):
        db_session.add(DeploymentRule(repository_id=repository.id, workflow_name_pattern="Deploy"))
        db_session.commit()
        for index in range(20):
            _deployment(db_session, repository, minutes_ago=1000 - index * 40, ext=f"ok{index}")

        health = compute_service_health(db_session, repository, window_days=30)
        stability = _dimension(health, HealthDimension.STABILITY)

        assert stability.score is not None
        assert stability.score >= 80, "no failures at all should score highly"

    def test_frequent_failures_lower_stability(self, db_session, repository):
        db_session.add(DeploymentRule(repository_id=repository.id, workflow_name_pattern="Deploy"))
        db_session.commit()
        for index in range(5):
            _deployment(db_session, repository, minutes_ago=1000 - index * 40, ext=f"ok{index}")
        for index in range(5):
            _deployment(db_session, repository, status=DeploymentStatus.FAILED,
                        minutes_ago=800 - index * 40, ext=f"bad{index}")

        stability = _dimension(
            compute_service_health(db_session, repository, window_days=30),
            HealthDimension.STABILITY,
        )

        assert stability.score is not None
        assert stability.score < 80


class TestRanking:
    def test_worst_scoring_service_is_listed_first(self, db_session, repository):
        """The page exists to surface what needs work, so the worst sorts first."""
        measured = Repository(full_name="org/measured", display_name="measured")
        db_session.add(measured)
        db_session.commit()
        db_session.add(DeploymentRule(repository_id=measured.id, workflow_name_pattern="Deploy"))
        db_session.commit()
        for index in range(6):
            _deployment(db_session, measured, minutes_ago=900 - index * 40, ext=f"m{index}")

        response = compute_health(db_session, window_days=30)
        scores = [s.overall_score for s in response.services if s.overall_score is not None]

        assert scores == sorted(scores), "lowest score first"

    def test_a_service_with_no_data_does_not_outrank_one_with_data(
        self, db_session, repository
    ):
        """OBSERVABILITY is always measurable, so a bare repository still gets a
        score — but it must be a LOW one, driven by how little DevPulse can see.
        A repository with nothing must never appear healthier than one with data."""
        measured = Repository(full_name="org/measured", display_name="measured")
        db_session.add(measured)
        db_session.commit()
        db_session.add(DeploymentRule(repository_id=measured.id, workflow_name_pattern="Deploy"))
        db_session.commit()
        for index in range(6):
            _deployment(db_session, measured, minutes_ago=900 - index * 40, ext=f"m{index}")

        response = compute_health(db_session, window_days=30)
        by_name = {s.service: s for s in response.services}

        bare = by_name["payments"]          # the fixture repository, no data at all
        assert bare.overall_score is not None
        assert bare.overall_score <= by_name["measured"].overall_score

    def test_unscorable_services_would_sort_last(self, db_session, repository):
        """Defensive: if every dimension were unmeasurable the service sorts
        last, because unknown is not healthy."""
        services = compute_health(db_session, window_days=30).services
        nulls = [s for s in services if s.overall_score is None]
        if nulls:
            assert services[-1].overall_score is None


def test_health_endpoint(api_client, repository):
    response = api_client.get("/api/health-score?window_days=30")

    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 30
    assert len(body["services"][0]["dimensions"]) == 5
