"""Anomaly detection (PRD 2.10).

Detection must be conservative. A surface that cries wolf gets ignored, and an
ignored surface is worse than none — so most of these tests are about what does
NOT get reported.
"""

from datetime import timedelta

import pytest

from app.models.events import Anomaly
from app.schemas.anomalies import AnomalyDirection, AnomalySeverity
from app.services.anomalies import (
    MIN_REPORTABLE_PCT,
    acknowledge,
    detect_anomalies,
    list_anomalies,
)
from tests.conftest import NOW


def _delivery(db, repository, runs, *, number, review_minutes, ci_minutes, days_ago):
    merged_minutes_ago = days_ago * 24 * 60
    pr = runs.add_merged_pr(
        number=number,
        merged_minutes_ago=merged_minutes_ago,
        opened_minutes_ago=merged_minutes_ago + review_minutes,
    )
    pr.merge_commit_sha = f"sha{number}"
    db.commit()

    run = runs.add(
        workflow_name="CI", conclusion="success",
        started_minutes_ago=merged_minutes_ago, duration_minutes=ci_minutes,
    )
    run.head_sha = f"sha{number}"
    db.commit()


def _history(db, repository, runs, *, ci_baseline, ci_current):
    """Six baseline deliveries (8-26 days ago) and six recent ones (1-6 days)."""
    number = 1
    for offset in range(6):
        _delivery(db, repository, runs, number=number, review_minutes=30,
                  ci_minutes=ci_baseline, days_ago=8 + offset * 3)
        number += 1
    for offset in range(6):
        _delivery(db, repository, runs, number=number, review_minutes=30,
                  ci_minutes=ci_current, days_ago=1 + offset * 0.5)
        number += 1


class TestDetection:
    def test_a_large_regression_is_detected(self, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)

        response = list_anomalies(db_session, window_days=7)

        ci = next(a for a in response.anomalies if a.metric == "ci_duration_minutes")
        assert ci.direction is AnomalyDirection.INCREASE
        assert ci.change_pct == pytest.approx(242.9, abs=1.0)
        assert ci.severity is AnomalySeverity.HIGH

    def test_the_anomaly_carries_its_evidence(self, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)

        ci = next(
            a for a in list_anomalies(db_session, window_days=7).anomalies
            if a.metric == "ci_duration_minutes"
        )

        assert any("Median ci duration" in item for item in ci.evidence)
        assert any("preceding" in item for item in ci.evidence)
        assert ci.baseline_sample_count >= 5

    def test_severity_scales_with_magnitude(self, db_session, repository, runs):
        # 7 -> 14 is +100%: meaningful, but not a tripling.
        _history(db_session, repository, runs, ci_baseline=7, ci_current=14)

        ci = next(
            a for a in list_anomalies(db_session, window_days=7).anomalies
            if a.metric == "ci_duration_minutes"
        )
        assert ci.severity is AnomalySeverity.MEDIUM


class TestConservatism:
    def test_normal_variation_is_not_reported(self, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=8)

        response = list_anomalies(db_session, window_days=7)

        assert not any(a.metric == "ci_duration_minutes" for a in response.anomalies)

    def test_an_improvement_is_not_an_anomaly(self, db_session, repository, runs):
        """CI getting three times faster is good news. Reporting it would train
        people to ignore the page."""
        _history(db_session, repository, runs, ci_baseline=24, ci_current=7)

        response = list_anomalies(db_session, window_days=7)

        assert not any(a.metric == "ci_duration_minutes" for a in response.anomalies)

    def test_without_enough_history_nothing_is_claimed(self, db_session, repository, runs):
        _delivery(db_session, repository, runs, number=1, review_minutes=30,
                  ci_minutes=7, days_ago=10)
        _delivery(db_session, repository, runs, number=2, review_minutes=30,
                  ci_minutes=90, days_ago=1)

        response = list_anomalies(db_session, window_days=7)

        assert response.anomalies == []
        assert "history to compare against" in response.unavailable_reason

    def test_the_reporting_floor_is_respected(self, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=100, ci_current=110)  # +10%

        response = list_anomalies(db_session, window_days=7)

        assert all(abs(a.change_pct) >= MIN_REPORTABLE_PCT for a in response.anomalies)


class TestPersistence:
    def test_rerunning_detection_refreshes_rather_than_duplicates(
        self, db_session, repository, runs
    ):
        """Detection runs on every page load; it must be idempotent."""
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)

        detect_anomalies(db_session, window_days=7)
        first = db_session.query(Anomaly).count()
        detect_anomalies(db_session, window_days=7)

        assert db_session.query(Anomaly).count() == first

    def test_an_anomaly_can_be_acknowledged(self, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)
        detect_anomalies(db_session, window_days=7)
        anomaly = db_session.query(Anomaly).first()

        acknowledge(db_session, anomaly.id)

        assert anomaly.acknowledged_at is not None

    def test_the_record_survives_the_metric_returning_to_normal(
        self, db_session, repository, runs
    ):
        """A derived-only anomaly could never answer "when did this start?"."""
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)
        detect_anomalies(db_session, window_days=7)

        stored = db_session.query(Anomaly).count()
        assert stored > 0
        # Detection over a window with no data must not erase history.
        detect_anomalies(db_session, window_days=1)
        assert db_session.query(Anomaly).count() >= stored


class TestApi:
    def test_endpoint_returns_anomalies(self, api_client, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)

        response = api_client.get("/api/anomalies?window_days=7")

        assert response.status_code == 200
        assert response.json()["anomalies"]

    def test_acknowledge_endpoint(self, api_client, db_session, repository, runs):
        _history(db_session, repository, runs, ci_baseline=7, ci_current=24)
        api_client.get("/api/anomalies?window_days=7")
        anomaly_id = db_session.query(Anomaly).first().id

        assert api_client.post(f"/api/anomalies/{anomaly_id}/acknowledge").status_code == 204
        assert api_client.post("/api/anomalies/9999/acknowledge").status_code == 404
