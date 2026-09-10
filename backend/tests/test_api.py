"""API contract tests.

These assert the shape of the HTTP surface, which the frontend depends on, so a
later refactor cannot silently change the contract.
"""

import pytest


def test_health_endpoint_reports_ok(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dora_endpoint_returns_an_empty_service_list_when_nothing_is_tracked(api_client):
    response = api_client.get("/api/metrics/dora")

    assert response.status_code == 200
    assert response.json() == {"window_days": 30, "services": []}


def test_dora_endpoint_reports_each_tracked_service(api_client, repository, runs):
    runs.add(conclusion="success", started_minutes_ago=60)

    response = api_client.get("/api/metrics/dora?window_days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 7
    assert len(body["services"]) == 1

    service = body["services"][0]
    assert service["service"] == "payments"
    assert service["total_deployments"] == 1
    # Every field the frontend's ServiceDoraMetrics type expects must be present.
    assert set(service) == {
        "service",
        "deployment_frequency_per_week",
        "lead_time_hours",
        "change_failure_rate_pct",
        "mttr_hours",
        "total_deployments",
        "total_failures",
    }


@pytest.mark.parametrize("window_days", [0, 366, -1])
def test_dora_endpoint_rejects_windows_outside_the_supported_range(
    api_client, window_days
):
    response = api_client.get(f"/api/metrics/dora?window_days={window_days}")

    assert response.status_code == 422
