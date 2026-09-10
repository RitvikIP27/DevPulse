"""Cross-system conflict detection (PRD 2.11-2.13, testing.md 15/18).

The scenarios here are the ones the product exists for. Scenario F and G from
testing.md 18 in particular: a deployment that succeeds while the application it
shipped degrades, and a control plane that disagrees with monitoring.
"""

from datetime import timedelta

import pytest

from app.models.events import Deployment, Incident, RuntimeObservation
from app.schemas.conflicts import ConflictType, RelationStrength
from app.services.conflicts import (
    COMPARISON_WINDOW_MINUTES,
    build_reports,
    compare_runtime_around,
)
from app.services.deployments import PROVIDER_CONFIGURED_WORKFLOW, DeploymentStatus
from tests.conftest import NOW


@pytest.fixture
def monitoring_connected(monkeypatch):
    """Pretend a Prometheus URL is configured, without making a network call."""
    monkeypatch.setattr("app.connectors.prometheus.is_configured", lambda: True)


@pytest.fixture
def incidents_connected(monkeypatch):
    monkeypatch.setattr("app.connectors.pagerduty.is_configured", lambda: True)


def _deployment(db, repository, *, status=DeploymentStatus.SUCCESS, minutes_ago=60):
    deployment = Deployment(
        repository_id=repository.id,
        provider=PROVIDER_CONFIGURED_WORKFLOW,
        external_id=f"dep-{minutes_ago}",
        environment="production",
        is_production=True,
        commit_sha="abc123",
        status=status,
        started_at=NOW - timedelta(minutes=minutes_ago + 3),
        finished_at=NOW - timedelta(minutes=minutes_ago),
    )
    db.add(deployment)
    db.commit()
    return deployment


def _samples(db, repository, deployment, metric, before, after):
    """Runtime samples either side of the deployment's completion."""
    anchor = deployment.finished_at
    for index, value in enumerate(before):
        db.add(RuntimeObservation(
            repository_id=repository.id, provider="prometheus", environment="production",
            metric=metric, value=value, observed_at=anchor - timedelta(minutes=index + 1),
        ))
    for index, value in enumerate(after):
        db.add(RuntimeObservation(
            repository_id=repository.id, provider="prometheus", environment="production",
            metric=metric, value=value, observed_at=anchor + timedelta(minutes=index + 1),
        ))
    db.commit()


class TestRuntimeUnavailable:
    def test_without_monitoring_the_comparison_says_so(self, db_session, repository):
        deployment = _deployment(db_session, repository)

        comparison = compare_runtime_around(db_session, deployment)

        assert comparison.available is False
        assert "cannot determine" in comparison.unavailable_reason

    def test_a_successful_deployment_is_never_reported_as_healthy_without_evidence(
        self, db_session, repository
    ):
        """testing.md 16: absent monitoring must reduce coverage, not manufacture
        a clean bill of health."""
        _deployment(db_session, repository)

        response = build_reports(db_session, window_days=30)

        assert response.runtime_available is False
        assert response.conflict_count == 0
        assert "cannot determine whether production stayed healthy" in response.unavailable_reason

    def test_monitoring_connected_but_no_samples_is_distinguished(
        self, db_session, repository, monitoring_connected
    ):
        deployment = _deployment(db_session, repository)

        comparison = compare_runtime_around(db_session, deployment)

        assert comparison.available is False
        assert "no runtime samples" in comparison.unavailable_reason


class TestScenarioF_RuntimeRegressionAfterSuccessfulDeployment:
    """Deployment succeeds, application starts failing."""

    @pytest.fixture
    def report(self, db_session, repository, monitoring_connected):
        deployment = _deployment(db_session, repository)
        _samples(db_session, repository, deployment, "error_rate_pct",
                 before=[0.8, 0.7, 0.9, 0.8], after=[18.4, 17.9, 19.1, 18.0])
        return build_reports(db_session, window_days=30).reports[0]

    def test_the_degradation_is_detected(self, report):
        shift = next(s for s in report.runtime.shifts if s.metric == "error_rate_pct")
        assert shift.is_degradation is True
        assert shift.before_value == pytest.approx(0.8, abs=0.05)
        assert shift.after_value == pytest.approx(18.2, abs=0.5)

    def test_a_conflict_is_raised_not_a_healthy_verdict(self, report):
        assert report.deployment_status == DeploymentStatus.SUCCESS
        assert any(
            conflict.type is ConflictType.DEPLOYMENT_SUCCESS_RUNTIME_DEGRADED
            for conflict in report.conflicts
        )

    def test_the_conflict_quotes_both_systems(self, report):
        conflict = report.conflicts[0]
        assert any("reported SUCCESS" in item for item in conflict.evidence)
        assert any("error_rate_pct moved" in item for item in conflict.evidence)

    def test_it_never_claims_causation(self, report):
        """rules.md 10 / ADR-011: X before Y is not X caused Y."""
        conflict = report.conflicts[0]
        assert conflict.strength in (RelationStrength.CORRELATED, RelationStrength.POTENTIALLY_RELATED)
        joined = " ".join(conflict.evidence + [conflict.description]).lower()
        assert "caused" not in joined
        assert any("caused the degradation, or the two merely" in u for u in conflict.unknowns)

    def test_it_states_what_remains_unknown(self, report):
        assert report.conflicts[0].unknowns


class TestNoFalsePositives:
    def test_stable_runtime_after_a_deployment_raises_no_conflict(
        self, db_session, repository, monitoring_connected
    ):
        deployment = _deployment(db_session, repository)
        _samples(db_session, repository, deployment, "error_rate_pct",
                 before=[0.8, 0.7, 0.9, 0.8], after=[0.8, 0.9, 0.7, 0.8])

        report = build_reports(db_session, window_days=30).reports[0]

        assert report.conflicts == []

    def test_an_improvement_is_not_a_degradation(
        self, db_session, repository, monitoring_connected
    ):
        deployment = _deployment(db_session, repository)
        _samples(db_session, repository, deployment, "error_rate_pct",
                 before=[9.0, 9.5, 8.5, 9.0], after=[0.5, 0.4, 0.6, 0.5])

        report = build_reports(db_session, window_days=30).reports[0]

        shift = next(s for s in report.runtime.shifts if s.metric == "error_rate_pct")
        assert shift.change_pct < 0
        assert shift.is_degradation is False
        assert report.conflicts == []

    def test_too_few_samples_yield_no_verdict(
        self, db_session, repository, monitoring_connected
    ):
        """Two points either side is an anecdote, not a shift."""
        deployment = _deployment(db_session, repository)
        _samples(db_session, repository, deployment, "error_rate_pct",
                 before=[0.8], after=[18.0])

        report = build_reports(db_session, window_days=30).reports[0]

        shift = next(s for s in report.runtime.shifts if s.metric == "error_rate_pct")
        assert shift.is_degradation is False
        assert report.conflicts == []


class TestScenarioG_IncidentAfterSuccessfulDeployment:
    def test_an_incident_shortly_after_success_is_surfaced(
        self, db_session, repository, incidents_connected
    ):
        deployment = _deployment(db_session, repository)
        db_session.add(Incident(
            repository_id=repository.id, provider="pagerduty", external_id="921",
            title="Elevated payment failures", status="TRIGGERED",
            started_at=deployment.finished_at + timedelta(minutes=4),
        ))
        db_session.commit()

        report = build_reports(db_session, window_days=30).reports[0]

        assert report.incidents_after == 1
        conflict = next(
            c for c in report.conflicts
            if c.type is ConflictType.DEPLOYMENT_SUCCESS_INCIDENT_OPENED
        )
        # An incident near a deployment is an association for a human to judge.
        assert conflict.strength is RelationStrength.POTENTIALLY_RELATED
        assert any("Elevated payment failures" in item for item in conflict.evidence)

    def test_an_incident_long_after_a_deployment_is_not_associated(
        self, db_session, repository, incidents_connected
    ):
        deployment = _deployment(db_session, repository)
        db_session.add(Incident(
            repository_id=repository.id, provider="pagerduty", external_id="922",
            title="Unrelated outage", status="TRIGGERED",
            started_at=deployment.finished_at + timedelta(hours=9),
        ))
        db_session.commit()

        reports = build_reports(db_session, window_days=30).reports

        # A deployment with nothing to report is omitted entirely, so assert on
        # the whole response rather than assuming a row exists.
        assert all(report.incidents_after == 0 for report in reports)
        assert all(report.conflicts == [] for report in reports)


def test_conflicts_endpoint_reports_provider_availability(api_client, db_session, repository):
    _deployment(db_session, repository)

    response = api_client.get("/api/conflicts")

    assert response.status_code == 200
    body = response.json()
    assert body["runtime_available"] is False
    assert body["incidents_available"] is False
    assert body["unavailable_reason"]
