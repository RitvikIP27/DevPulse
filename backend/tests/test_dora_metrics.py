"""Tests for the MVP delivery-metrics engine.

Two kinds of test live here.

Tests of behaviour that is genuinely correct today — the statistical arithmetic,
window filtering and run selection — guard against regression while the engine is
refactored in later stages.

Tests marked ``known_defect`` assert the behaviour DevPulse is supposed to have,
and are expected to fail until the stage that fixes them lands. They are written
with ``strict=True`` so that the moment the defect is fixed, the suite fails and
demands the marker be removed. This keeps the audit's findings encoded in
executable form rather than only in prose.
"""

import pytest

from app.services.dora_metrics import compute_all_metrics, compute_service_metrics

PRODUCTION_DEPLOY_WORKFLOW = "Deploy to production"
CI_WORKFLOW = "CI"

# Ground truth from PRD.md section 5: a change merged at 10:00 and deployed to
# production at 11:15 has a lead time of 75 minutes.
GROUND_TRUTH_LEAD_TIME_MINUTES = 75.0


class TestDeploymentFrequency:
    def test_counts_only_successful_runs(self, db_session, repository, runs):
        runs.add(conclusion="success", started_minutes_ago=100)
        runs.add(conclusion="success", started_minutes_ago=90)
        runs.add(conclusion="failure", started_minutes_ago=80)
        runs.add(conclusion="cancelled", started_minutes_ago=70)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.total_deployments == 2

    def test_is_normalised_to_a_weekly_rate(self, db_session, repository, runs):
        for minutes_ago in range(10, 150, 10):  # 14 successful runs
            runs.add(conclusion="success", started_minutes_ago=minutes_ago)

        metrics = compute_service_metrics(db_session, repository, window_days=28)

        # 14 successes over 4 weeks
        assert metrics.deployment_frequency_per_week == pytest.approx(3.5)

    def test_runs_outside_the_window_are_excluded(self, db_session, repository, runs):
        minutes_per_day = 60 * 24
        runs.add(conclusion="success", started_minutes_ago=2 * minutes_per_day)
        runs.add(conclusion="success", started_minutes_ago=40 * minutes_per_day)

        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.total_deployments == 1

    def test_in_progress_runs_are_ignored(self, db_session, repository, runs):
        """A run with no completion timestamp has not produced an outcome yet."""
        runs.add(conclusion="success", started_minutes_ago=60)
        runs.add(conclusion=None, started_minutes_ago=30, duration_minutes=None)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.total_deployments == 1


class TestChangeFailureRate:
    def test_is_failures_over_all_completed_runs(self, db_session, repository, runs):
        runs.add(conclusion="success", started_minutes_ago=100)
        runs.add(conclusion="success", started_minutes_ago=90)
        runs.add(conclusion="success", started_minutes_ago=80)
        runs.add(conclusion="failure", started_minutes_ago=70)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.total_failures == 1
        assert metrics.change_failure_rate_pct == pytest.approx(25.0)

    def test_cancelled_runs_count_toward_the_denominator_but_not_failures(
        self, db_session, repository, runs
    ):
        runs.add(conclusion="success", started_minutes_ago=100)
        runs.add(conclusion="cancelled", started_minutes_ago=90)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.total_failures == 0
        assert metrics.change_failure_rate_pct == pytest.approx(0.0)


class TestRecoveryTime:
    def test_is_the_median_gap_from_failure_to_the_next_success(
        self, db_session, repository, runs
    ):
        # Failure completes 120m ago, next success starts 60m ago -> 60m recovery.
        runs.add(conclusion="failure", started_minutes_ago=125, duration_minutes=5)
        runs.add(conclusion="success", started_minutes_ago=60)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.mttr_hours == pytest.approx(1.0)

    def test_is_unavailable_when_a_failure_never_recovers(
        self, db_session, repository, runs
    ):
        runs.add(conclusion="success", started_minutes_ago=200)
        runs.add(conclusion="failure", started_minutes_ago=100)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.mttr_hours is None


class TestLeadTime:
    def test_is_unavailable_when_no_pull_request_was_merged(
        self, db_session, repository, runs
    ):
        runs.add(conclusion="success", started_minutes_ago=60)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.lead_time_hours is None

    def test_is_unavailable_when_nothing_deployed_after_the_merge(
        self, db_session, repository, runs
    ):
        runs.add(conclusion="success", started_minutes_ago=200)
        runs.add_merged_pr(number=1, merged_minutes_ago=100)

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.lead_time_hours is None


class TestServiceRanking:
    def test_worst_performing_service_is_listed_first(self, db_session):
        from app.models.events import Repository

        healthy = Repository(full_name="org/healthy", display_name="healthy")
        failing = Repository(full_name="org/failing", display_name="failing")
        db_session.add_all([healthy, failing])
        db_session.commit()

        from tests.conftest import RunBuilder

        RunBuilder(db_session, healthy).add(conclusion="success", started_minutes_ago=60)
        failing_runs = RunBuilder(db_session, failing)
        failing_runs.add(conclusion="failure", started_minutes_ago=60)
        failing_runs.add(conclusion="success", started_minutes_ago=50)

        response = compute_all_metrics(db_session, window_days=7)

        assert [service.service for service in response.services] == ["failing", "healthy"]
        assert response.window_days == 7


class TestKnownDefects:
    """Defects the Stage 0 audit proved with live data.

    Each test states the behaviour the product requires. They fail today on
    purpose; the stage named in each reason removes the marker.
    """

    @pytest.mark.known_defect
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "ADR-010 / audit finding 1: every workflow run is treated as a deployment. "
            "On the audited repository only 6 of 34 counted deployments were "
            "deployment-shaped. Fixed by Stage 5 (explicit deployment model)."
        ),
    )
    def test_a_ci_run_is_not_counted_as_a_production_deployment(
        self, db_session, repository, runs
    ):
        runs.add(workflow_name=CI_WORKFLOW, conclusion="success", started_minutes_ago=100)
        runs.add(workflow_name="Infrastructure", conclusion="success", started_minutes_ago=95)
        runs.add(
            workflow_name=PRODUCTION_DEPLOY_WORKFLOW,
            conclusion="success",
            started_minutes_ago=90,
        )

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.total_deployments == 1

    @pytest.mark.known_defect
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Audit finding 2: lead time matches the next successful run of ANY "
            "workflow, which is the CI job the merge itself triggered, so it "
            "collapses to ~0 for every PR. Fixed by Stage 7 (DORA engine v2)."
        ),
    )
    def test_lead_time_measures_merge_to_production_deployment(
        self, db_session, repository, runs
    ):
        runs.add_merged_pr(number=1, merged_minutes_ago=GROUND_TRUTH_LEAD_TIME_MINUTES)
        # CI fires seconds after the merge and must not satisfy the measurement.
        runs.add(
            workflow_name=CI_WORKFLOW,
            conclusion="success",
            started_minutes_ago=GROUND_TRUTH_LEAD_TIME_MINUTES - 0.1,
        )
        # The production deployment is what the metric is actually about.
        runs.add(
            workflow_name=PRODUCTION_DEPLOY_WORKFLOW,
            conclusion="success",
            started_minutes_ago=0,
        )

        metrics = compute_service_metrics(db_session, repository, window_days=7)

        assert metrics.lead_time_hours == pytest.approx(
            GROUND_TRUTH_LEAD_TIME_MINUTES / 60.0, abs=0.01
        )

    @pytest.mark.known_defect
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Audit finding 5 / PRD 2.6 / rules.md 11: a repository with no ingested "
            "data reports 0.0 and then sorts as the best-performing service. Absent "
            "data must be unavailable, not healthy. Fixed by Stage 6 (data coverage)."
        ),
    )
    def test_a_repository_with_no_data_reports_unavailable_not_zero(
        self, db_session, repository
    ):
        metrics = compute_service_metrics(db_session, repository, window_days=30)

        assert metrics.change_failure_rate_pct is None
        assert metrics.deployment_frequency_per_week is None
