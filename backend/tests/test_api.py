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
    # A CI run is not a deployment, so nothing is measurable here.
    assert service["deployment_source"] == "NONE"
    assert service["total_deployments"] == 0

    # Every field the frontend's ServiceDoraMetrics type expects must be present.
    assert set(service) == {
        "service",
        "deployment_source",
        "unavailable_reason",
        "deployment_frequency_per_week",
        "lead_time_hours",
        "change_failure_rate_pct",
        "failed_deployment_recovery_hours",
        "deployment_rework_rate_pct",
        "total_deployments",
        "total_failures",
    }


def test_deployment_rules_can_be_declared_and_removed(api_client, repository, runs):
    runs.add(workflow_name="Deploy to production", conclusion="success", started_minutes_ago=60)

    created = api_client.post(
        f"/api/repositories/{repository.id}/deployment-rules",
        json={"workflow_name_pattern": "Deploy to production"},
    )
    assert created.status_code == 201
    assert created.json()["deployment_source"] == "CONFIGURED_WORKFLOW"
    assert created.json()["rules"][0]["matched_run_count"] == 1

    # The rule immediately makes metrics measurable.
    metrics = api_client.get("/api/metrics/dora?window_days=7").json()["services"][0]
    assert metrics["total_deployments"] == 1

    rule_id = created.json()["rules"][0]["id"]
    assert api_client.delete(
        f"/api/repositories/{repository.id}/deployment-rules/{rule_id}"
    ).status_code == 204

    # Withdrawing the mapping withdraws the metrics built on it.
    after = api_client.get("/api/metrics/dora?window_days=7").json()["services"][0]
    assert after["deployment_source"] == "NONE"


def test_a_duplicate_deployment_rule_is_rejected(api_client, repository):
    payload = {"workflow_name_pattern": "Deploy"}
    assert api_client.post(f"/api/repositories/{repository.id}/deployment-rules", json=payload).status_code == 201
    assert api_client.post(f"/api/repositories/{repository.id}/deployment-rules", json=payload).status_code == 409


def test_deployment_rules_for_an_unknown_repository_are_404(api_client):
    assert api_client.get("/api/repositories/999/deployment-rules").status_code == 404


@pytest.mark.parametrize("window_days", [0, 366, -1])
def test_dora_endpoint_rejects_windows_outside_the_supported_range(
    api_client, window_days
):
    response = api_client.get(f"/api/metrics/dora?window_days={window_days}")

    assert response.status_code == 422
