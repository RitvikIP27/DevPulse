"""Synthetic reference scenarios (PRD 5, testing.md 17-18).

Creates a clearly marked demo repository so the runtime-regression and
deployment/runtime-conflict behaviour can be exercised without a real Prometheus
or PagerDuty. Demo data is never written to a real repository, and every record
carries a ``demo`` provider so it cannot be mistaken for ingested telemetry.

    python -m app.demo_seed          create or refresh the demo repository
    python -m app.demo_seed --clear  remove it entirely

Requires DEMO_MODE=true for the demo data to be readable by the UI.
"""

from __future__ import annotations

import sys
from datetime import timedelta

from app.core.database import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.models.events import (
    Deployment,
    Incident,
    PullRequest,
    Repository,
    RuntimeObservation,
    WorkflowRun,
)
from app.services.deployments import PROVIDER_CONFIGURED_WORKFLOW, DeploymentStatus
from app.services.timestamps import utc_now

logger = get_logger(__name__)

DEMO_REPO_FULL_NAME = "devpulse-demo/payments-api"
DEMO_REPO_DISPLAY_NAME = "payments-api (demo)"
DEMO_PROVIDER = "demo"


def _clear(db) -> None:
    repo = db.query(Repository).filter_by(full_name=DEMO_REPO_FULL_NAME).first()
    if repo is None:
        return
    for model in (RuntimeObservation, Incident, Deployment, WorkflowRun, PullRequest):
        db.query(model).filter_by(repository_id=repo.id).delete()
    db.delete(repo)
    db.commit()


def seed(clear_only: bool = False) -> None:
    db = SessionLocal()
    try:
        _clear(db)
        if clear_only:
            logger.info("demo data removed")
            return

        repo = Repository(full_name=DEMO_REPO_FULL_NAME, display_name=DEMO_REPO_DISPLAY_NAME)
        db.add(repo)
        db.commit()
        db.refresh(repo)

        now = utc_now()

        # Scenario A — a healthy delivery. Runtime stays flat across the deploy.
        # Scenario F — a deployment that succeeds while the application degrades.
        # Scenario G — an incident opening minutes after that same deployment.
        scenarios = [
            {"hours_ago": 30, "sha": "aaa111healthy", "pr": 480,
             "before": [0.8, 0.7, 0.9, 0.8, 0.8], "after": [0.8, 0.9, 0.7, 0.8, 0.8],
             "latency_before": [180, 190, 175, 185, 180],
             "latency_after": [182, 178, 186, 180, 181],
             "incident": None},
            {"hours_ago": 5, "sha": "bbb222regress", "pr": 482,
             "before": [0.8, 0.7, 0.9, 0.8, 0.8], "after": [18.4, 17.9, 19.1, 18.0, 18.6],
             "latency_before": [180, 190, 175, 185, 180],
             "latency_after": [910, 880, 950, 920, 905],
             "incident": "Elevated payment validation failures"},
        ]

        for index, scenario in enumerate(scenarios):
            deployed_at = now - timedelta(hours=scenario["hours_ago"])
            merged_at = deployed_at - timedelta(minutes=75)  # PRD ground truth: 75m lead time

            db.add(PullRequest(
                repository_id=repo.id, github_pr_number=scenario["pr"],
                title=f"Demo change #{scenario['pr']}",
                opened_at=merged_at - timedelta(hours=5), merged_at=merged_at, is_merged=True,
                merge_commit_sha=scenario["sha"], base_branch="main",
                head_branch=f"demo/{scenario['pr']}", author_login="demo-engineer",
            ))
            db.add(WorkflowRun(
                repository_id=repo.id, github_run_id=f"demo-run-{index}",
                workflow_name="CI", conclusion="success", status="completed",
                started_at=merged_at, completed_at=merged_at + timedelta(minutes=8),
                head_sha=scenario["sha"], head_branch="main", event="push",
            ))
            db.add(Deployment(
                repository_id=repo.id, provider=PROVIDER_CONFIGURED_WORKFLOW,
                external_id=f"demo-deploy-{index}", environment="production",
                is_production=True, commit_sha=scenario["sha"],
                status=DeploymentStatus.SUCCESS,
                started_at=deployed_at - timedelta(minutes=3), finished_at=deployed_at,
            ))

            for metric, before, after in (
                ("error_rate_pct", scenario["before"], scenario["after"]),
                ("latency_p95_ms", scenario["latency_before"], scenario["latency_after"]),
            ):
                for offset, value in enumerate(before, start=1):
                    db.add(RuntimeObservation(
                        repository_id=repo.id, provider=DEMO_PROVIDER, environment="production",
                        metric=metric, value=value,
                        observed_at=deployed_at - timedelta(minutes=offset * 4),
                    ))
                for offset, value in enumerate(after, start=1):
                    db.add(RuntimeObservation(
                        repository_id=repo.id, provider=DEMO_PROVIDER, environment="production",
                        metric=metric, value=value,
                        observed_at=deployed_at + timedelta(minutes=offset * 4),
                    ))

            if scenario["incident"]:
                db.add(Incident(
                    repository_id=repo.id, provider=DEMO_PROVIDER,
                    external_id=f"demo-incident-{index}", title=scenario["incident"],
                    severity="P2", status="RESOLVED",
                    started_at=deployed_at + timedelta(minutes=4),
                    resolved_at=deployed_at + timedelta(minutes=31),
                ))

        db.commit()
        logger.info(
            "demo repository %s seeded with %d scenarios", DEMO_REPO_FULL_NAME, len(scenarios)
        )
        print(
            f"Seeded {DEMO_REPO_FULL_NAME}.\n"
            "Set DEMO_MODE=true in backend/.env and restart the backend to view it."
        )
    finally:
        db.close()


if __name__ == "__main__":
    configure_logging()
    seed(clear_only="--clear" in sys.argv)
