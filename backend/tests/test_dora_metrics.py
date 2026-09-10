"""DORA metrics computed from deployments (PRD 2.7, ADR-010).

Ground-truth scenarios from PRD section 5 are asserted directly: a change merged
at a known time and deployed at a known time must produce the stated lead time.

The tests previously marked ``known_defect`` for CI-as-deployment and for lead
time are now ordinary passing tests. That was the point of ADR-016: the markers
had to be removed the moment the behaviour was fixed.
"""

from datetime import timedelta

import pytest

from app.models.events import Deployment, DeploymentRule, Repository
from app.services.deployments import (
    DeploymentSource,
    DeploymentStatus,
    PROVIDER_CONFIGURED_WORKFLOW,
    derive_deployments_from_rules,
)
from app.services.dora_metrics import compute_all_metrics, compute_service_metrics
from tests.conftest import NOW

PRODUCTION_DEPLOY_WORKFLOW = "Deploy to production"
CI_WORKFLOW = "CI"

# PRD section 5: merged at 10:00, deployed at 11:15 -> 75 minutes.
GROUND_TRUTH_LEAD_TIME_MINUTES = 75.0


def _add_deployment(db, repository, *, status, started_minutes_ago, commit_sha=None, external_id=None):
    deployment = Deployment(
        repository_id=repository.id,
        provider=PROVIDER_CONFIGURED_WORKFLOW,
        external_id=external_id or f"dep-{started_minutes_ago}-{status}",
        environment="production",
        is_production=True,
        commit_sha=commit_sha,
        status=status,
        started_at=NOW - timedelta(minutes=started_minutes_ago),
        finished_at=NOW - timedelta(minutes=started_minutes_ago - 2),
    )
    db.add(deployment)
    db.commit()
    return deployment


class TestNoDeploymentSource:
    def test_metrics_are_unavailable_rather_than_zero(self, db_session, repository, runs):
        """The defect the audit found: a repository with no deployment data
        reported 0.0 and then sorted as the best-performing service."""
        runs.add(workflow_name=CI_WORKFLOW, conclusion="success", started_minutes_ago=60)

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.deployment_source == DeploymentSource.NONE
        assert metrics.deployment_frequency_per_week is None
        assert metrics.change_failure_rate_pct is None
        assert metrics.lead_time_hours is None
        assert "cannot identify production deployments" in metrics.unavailable_reason

    def test_a_ci_run_is_not_counted_as_a_production_deployment(self, db_session, repository, runs):
        """Previously xfail. On the audited repository only 6 of 34 counted
        deployments were deployment-shaped."""
        runs.add(workflow_name=CI_WORKFLOW, conclusion="success", started_minutes_ago=100)
        runs.add(workflow_name="Infrastructure", conclusion="success", started_minutes_ago=95)

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.total_deployments == 0

    def test_unmeasurable_services_never_top_the_worst_first_ranking(self, db_session, runs, repository):
        """A service with no data is not a healthy service."""
        failing = Repository(full_name="org/failing", display_name="failing")
        db_session.add(failing)
        db_session.commit()
        _add_deployment(db_session, failing, status=DeploymentStatus.FAILED, started_minutes_ago=60)
        _add_deployment(db_session, failing, status=DeploymentStatus.SUCCESS, started_minutes_ago=30)

        response = compute_all_metrics(db_session, window_days=30)

        assert response.services[0].service == "failing"
        assert response.services[-1].change_failure_rate_pct is None


class TestConfiguredDeploymentWorkflow:
    def test_only_the_declared_workflow_becomes_a_deployment(self, db_session, repository, runs):
        runs.add(workflow_name=CI_WORKFLOW, conclusion="success", started_minutes_ago=100)
        runs.add(workflow_name="Infrastructure", conclusion="success", started_minutes_ago=95)
        runs.add(workflow_name=PRODUCTION_DEPLOY_WORKFLOW, conclusion="success", started_minutes_ago=90)
        db_session.add(DeploymentRule(repository_id=repository.id, workflow_name_pattern="Deploy to production"))
        db_session.commit()

        derive_deployments_from_rules(db_session, repository)
        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.deployment_source == DeploymentSource.CONFIGURED_WORKFLOW
        assert metrics.total_deployments == 1

    def test_a_cancelled_run_is_neither_a_success_nor_a_failure(self, db_session, repository, runs):
        runs.add(workflow_name=PRODUCTION_DEPLOY_WORKFLOW, conclusion="cancelled", started_minutes_ago=90)
        db_session.add(DeploymentRule(repository_id=repository.id, workflow_name_pattern="Deploy"))
        db_session.commit()

        derive_deployments_from_rules(db_session, repository)

        assert db_session.query(Deployment).count() == 0


class TestLeadTime:
    def test_measures_merge_to_the_deployment_that_shipped_the_commit(self, db_session, repository, runs):
        """Previously xfail. The MVP matched the next successful run after a
        merge, which was always the CI job that merge triggered, so lead time
        collapsed to roughly 0.1 minutes for every pull request."""
        pr = runs.add_merged_pr(number=1, merged_minutes_ago=GROUND_TRUTH_LEAD_TIME_MINUTES)
        pr.merge_commit_sha = "abc123"
        db_session.commit()

        # CI fires seconds after the merge and must not satisfy the measurement.
        runs.add(
            workflow_name=CI_WORKFLOW,
            conclusion="success",
            started_minutes_ago=GROUND_TRUTH_LEAD_TIME_MINUTES - 0.1,
        )
        _add_deployment(
            db_session, repository, status=DeploymentStatus.SUCCESS,
            started_minutes_ago=0, commit_sha="abc123",
        )

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.lead_time_hours == pytest.approx(GROUND_TRUTH_LEAD_TIME_MINUTES / 60.0, abs=0.01)

    def test_a_deployment_of_an_uncorrelated_commit_is_not_measured(self, db_session, repository, runs):
        pr = runs.add_merged_pr(number=1, merged_minutes_ago=75)
        pr.merge_commit_sha = "abc123"
        db_session.commit()
        _add_deployment(
            db_session, repository, status=DeploymentStatus.SUCCESS,
            started_minutes_ago=0, commit_sha="unrelated999",
        )

        assert compute_service_metrics(db_session, repository, window_days=30).lead_time_hours is None


class TestChangeFailureRate:
    def test_is_failed_over_concluded_production_deployments(self, db_session, repository):
        for i in range(3):
            _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                            started_minutes_ago=100 - i, external_id=f"s{i}")
        _add_deployment(db_session, repository, status=DeploymentStatus.FAILED,
                        started_minutes_ago=60, external_id="f0")

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.change_failure_rate_pct == pytest.approx(25.0)
        assert metrics.total_deployments == 3
        assert metrics.total_failures == 1


class TestRecoveryTime:
    def test_measures_failed_deployment_to_the_next_successful_one(self, db_session, repository):
        # PRD section 5 ground truth: failed at 12:00, recovered at 12:30 -> 30m.
        _add_deployment(db_session, repository, status=DeploymentStatus.FAILED,
                        started_minutes_ago=122, external_id="f")
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=90, external_id="s")

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.failed_deployment_recovery_hours == pytest.approx(0.5, abs=0.01)

    def test_a_success_long_after_a_failure_is_not_treated_as_its_recovery(self, db_session, repository):
        """Beyond the recovery window the two deployments are unrelated, and
        calling the later one a recovery would invent a causal link."""
        _add_deployment(db_session, repository, status=DeploymentStatus.FAILED,
                        started_minutes_ago=60 * 24 * 10, external_id="f")
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=60, external_id="s")

        assert compute_service_metrics(
            db_session, repository, window_days=90
        ).failed_deployment_recovery_hours is None


class TestReworkRate:
    def test_counts_deployments_that_followed_a_failure(self, db_session, repository):
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=200, external_id="a")
        _add_deployment(db_session, repository, status=DeploymentStatus.FAILED,
                        started_minutes_ago=150, external_id="b")
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=100, external_id="c")
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=50, external_id="d")

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        # One of four production deployments remediated a failure.
        assert metrics.deployment_rework_rate_pct == pytest.approx(25.0)


class TestWindow:
    def test_deployments_outside_the_window_are_excluded(self, db_session, repository):
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=60 * 24 * 2, external_id="recent")
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=60 * 24 * 40, external_id="old")

        assert compute_service_metrics(db_session, repository, window_days=30).total_deployments == 1

    def test_a_window_with_no_deployments_reports_why(self, db_session, repository):
        _add_deployment(db_session, repository, status=DeploymentStatus.SUCCESS,
                        started_minutes_ago=60 * 24 * 40, external_id="old")

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.deployment_frequency_per_week is None
        assert "No production deployment completed" in metrics.unavailable_reason
