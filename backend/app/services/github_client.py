"""
Pulls pull-request and workflow-run data from the GitHub REST API for every
repo listed in GITHUB_REPOS, and upserts it into Postgres.

Run manually with:
    python -m app.services.github_client

Or wire it to a scheduled job / GitHub webhook for near-real-time ingestion.
"""

from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.events import Repository, PullRequest, WorkflowRun

GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def get_or_create_repository(
    db: Session,
    full_name: str,
) -> Repository:
    repo = db.query(Repository).filter_by(full_name=full_name).first()

    if repo:
        return repo

    repo = Repository(
        full_name=full_name,
        display_name=full_name.split("/")[-1],
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return repo


def sync_pull_requests(
    db: Session,
    repo: Repository,
    client: httpx.Client,
    pages: int = 3,
):
    """
    Fetch all pull requests for the repository and upsert them into Postgres.
    """

    for page in range(1, pages + 1):
        response = client.get(
            f"{GITHUB_API}/repos/{repo.full_name}/pulls",
            params={
                "state": "all",
                "per_page": 50,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            },
        )

        response.raise_for_status()

        items = response.json()

        if not items:
            break

        for pr in items:
            existing = (
                db.query(PullRequest)
                .filter_by(
                    repository_id=repo.id,
                    github_pr_number=pr["number"],
                )
                .first()
            )

            opened_at = _parse_dt(pr.get("created_at"))
            merged_at = _parse_dt(pr.get("merged_at"))

            if existing:
                existing.title = pr.get("title")
                existing.opened_at = opened_at
                existing.merged_at = merged_at
                existing.is_merged = merged_at is not None

            else:
                db.add(
                    PullRequest(
                        repository_id=repo.id,
                        github_pr_number=pr["number"],
                        title=pr.get("title"),
                        opened_at=opened_at,
                        merged_at=merged_at,
                        is_merged=merged_at is not None,
                    )
                )

        db.commit()


def sync_workflow_runs(
    db: Session,
    repo: Repository,
    client: httpx.Client,
    pages: int = 3,
):
    """
    Fetch GitHub Actions workflow runs and upsert ALL workflow runs
    into Postgres.

    No workflow-name filtering is applied. Every workflow run is stored.
    """

    for page in range(1, pages + 1):
        response = client.get(
            f"{GITHUB_API}/repos/{repo.full_name}/actions/runs",
            params={
                "per_page": 50,
                "page": page,
            },
        )

        response.raise_for_status()

        data = response.json()
        runs = data.get("workflow_runs", [])

        if not runs:
            break

        for run in runs:
            name = run.get("name", "")

            existing = (
                db.query(WorkflowRun)
                .filter_by(
                    github_run_id=str(run["id"]),
                )
                .first()
            )

            started_at = _parse_dt(run.get("run_started_at"))

            completed_at = None

            if run.get("status") == "completed":
                completed_at = _parse_dt(run.get("updated_at"))

            if existing:
                existing.workflow_name = name
                existing.conclusion = run.get("conclusion")
                existing.started_at = started_at
                existing.completed_at = completed_at

            else:
                db.add(
                    WorkflowRun(
                        repository_id=repo.id,
                        github_run_id=str(run["id"]),
                        workflow_name=name,
                        conclusion=run.get("conclusion"),
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )

        db.commit()


def sync_all():
    """
    Sync every repository configured in GITHUB_REPOS.
    """

    if not settings.github_token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set — add it to backend/.env"
        )

    db = SessionLocal()

    try:
        with httpx.Client(
            headers=_headers(),
            timeout=30.0,
        ) as client:

            for full_name in settings.repo_list:
                repo = get_or_create_repository(
                    db,
                    full_name,
                )

                sync_pull_requests(
                    db,
                    repo,
                    client,
                )

                sync_workflow_runs(
                    db,
                    repo,
                    client,
                )

                print(f"synced {full_name}")

    finally:
        db.close()


if __name__ == "__main__":
    sync_all()