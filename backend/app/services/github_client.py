"""GitHub connector.

Fetches pull requests and Actions workflow runs, maps them onto DevPulse rows,
and records the outcome of every run as a SyncJob.

Per AGENTS.md 7 this module only collects and maps provider data. It contains no
metric calculation, no bottleneck logic and no knowledge of the dashboard.

Run manually with:
    python -m app.services.github_client
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterator

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.events import PullRequest, Repository, SyncJob, WorkflowRun
from app.connectors import pagerduty, prometheus
from app.services.deployments import derive_deployments_from_rules, sync_github_deployments
from app.services.errors import ConnectorError, ErrorCode, classify_http_error
from app.services.timestamps import parse_utc, utc_now

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 10  # bounds a first sync; incremental sync supersedes this later
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0
# GitHub keeps serving requests as the quota drains. Stopping while a small
# reserve remains leaves room for an interactive request to still succeed.
RATE_LIMIT_RESERVE = 10


class SyncStatus:
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """GET with bounded retries for transient failures.

    Rate limiting and server errors are retried because they are expected and
    recoverable. Authentication and permission failures are not: retrying a bad
    token only burns quota and delays the real error reaching the user.
    """
    last_error: ConnectorError | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            last_error = ConnectorError(ErrorCode.TIMEOUT, f"Timed out calling {url}.")
        except httpx.HTTPStatusError as error:
            connector_error = classify_http_error(error)
            if connector_error.code not in (ErrorCode.RATE_LIMIT, ErrorCode.PROVIDER_ERROR):
                raise connector_error from error
            last_error = connector_error
        except httpx.HTTPError as error:
            last_error = ConnectorError(ErrorCode.PROVIDER_ERROR, str(error))

        if attempt < MAX_RETRIES:
            delay = RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "github request failed (%s), retrying in %.1fs [attempt %d/%d] url=%s",
                last_error.code if last_error else "unknown", delay, attempt, MAX_RETRIES, url,
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def _paginate(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    extract: Callable[[Any], list[dict]],
) -> Iterator[dict]:
    """Yield items page by page, following GitHub's Link header.

    The MVP hard-coded three pages and silently truncated anything beyond 150
    records, which quietly understated activity on any busy repository.
    """
    page_params = {**params, "per_page": PER_PAGE}
    next_url: str | None = url
    pages = 0

    while next_url and pages < MAX_PAGES:
        response = _get(client, next_url, page_params if pages == 0 else None)
        items = extract(response.json())
        if not items:
            return

        yield from items
        pages += 1

        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is not None and remaining.isdigit() and int(remaining) <= RATE_LIMIT_RESERVE:
            logger.warning("stopping pagination early: rate-limit reserve reached (%s left)", remaining)
            return

        next_url = response.links.get("next", {}).get("url")

    if next_url:
        logger.info("stopped at the %d-page ceiling for %s; older records were not fetched", MAX_PAGES, url)


def get_or_create_repository(db: Session, full_name: str) -> Repository:
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if repo:
        return repo

    repo = Repository(full_name=full_name, display_name=full_name.split("/")[-1])
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def sync_pull_requests(db: Session, repo: Repository, client: httpx.Client) -> int:
    """Upsert pull requests. Returns the number of rows written."""
    written = 0

    for pr in _paginate(
        client,
        f"{GITHUB_API}/repos/{repo.full_name}/pulls",
        {"state": "all", "sort": "updated", "direction": "desc"},
        lambda payload: payload,
    ):
        opened_at = parse_utc(pr.get("created_at"))
        if opened_at is None:
            # opened_at is NOT NULL; a record without it cannot be stored, and
            # guessing a timestamp would corrupt every duration derived from it.
            logger.warning("skipping PR #%s in %s: no parseable created_at", pr.get("number"), repo.full_name)
            continue

        merged_at = parse_utc(pr.get("merged_at"))
        base = pr.get("base") or {}
        head = pr.get("head") or {}
        user = pr.get("user") or {}

        values = {
            "title": pr.get("title"),
            "opened_at": opened_at,
            "merged_at": merged_at,
            "is_merged": merged_at is not None,
            "head_sha": head.get("sha"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "base_branch": base.get("ref"),
            "head_branch": head.get("ref"),
            "author_login": user.get("login"),
            "closed_at": parse_utc(pr.get("closed_at")),
            "html_url": pr.get("html_url"),
        }

        existing = (
            db.query(PullRequest)
            .filter_by(repository_id=repo.id, github_pr_number=pr["number"])
            .first()
        )
        if existing:
            for field, value in values.items():
                setattr(existing, field, value)
        else:
            db.add(PullRequest(repository_id=repo.id, github_pr_number=pr["number"], **values))
        written += 1

    db.commit()
    return written


def sync_workflow_runs(db: Session, repo: Repository, client: httpx.Client) -> int:
    """Upsert Actions workflow runs. Returns the number of rows written.

    Every run is stored, including non-deployment workflows. Deciding which runs
    represent a production deployment is a delivery-semantics question and does
    not belong in a connector (ADR-010).
    """
    written = 0

    for run in _paginate(
        client,
        f"{GITHUB_API}/repos/{repo.full_name}/actions/runs",
        {},
        lambda payload: payload.get("workflow_runs", []),
    ):
        started_at = parse_utc(run.get("run_started_at")) or parse_utc(run.get("created_at"))
        if started_at is None:
            logger.warning("skipping run %s in %s: no parseable start time", run.get("id"), repo.full_name)
            continue

        is_completed = run.get("status") == "completed"
        values = {
            "workflow_name": run.get("name") or run.get("path") or "unnamed workflow",
            "conclusion": run.get("conclusion"),
            "started_at": started_at,
            "completed_at": parse_utc(run.get("updated_at")) if is_completed else None,
            "head_sha": run.get("head_sha"),
            "head_branch": run.get("head_branch"),
            "event": run.get("event"),
            "status": run.get("status"),
            "run_attempt": run.get("run_attempt"),
            "html_url": run.get("html_url"),
        }

        existing = db.query(WorkflowRun).filter_by(github_run_id=str(run["id"])).first()
        if existing:
            for field, value in values.items():
                setattr(existing, field, value)
        else:
            db.add(WorkflowRun(repository_id=repo.id, github_run_id=str(run["id"]), **values))
        written += 1

    db.commit()
    return written


def sync_repository(db: Session, full_name: str, client: httpx.Client) -> SyncJob:
    """Sync one repository, recording the outcome whether it succeeds or not."""
    repo = get_or_create_repository(db, full_name)
    job = SyncJob(
        repository_id=repo.id,
        provider="github",
        status=SyncStatus.RUNNING,
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()

    try:
        job.pull_requests_written = sync_pull_requests(db, repo, client)
        job.workflow_runs_written = sync_workflow_runs(db, repo, client)

        # Deployments come from the provider where it has them; otherwise from
        # rules the user declared. Never inferred from CI runs (ADR-010).
        provider_deployments = sync_github_deployments(db, repo, client)
        derived = derive_deployments_from_rules(db, repo) if not provider_deployments else 0
        logger.info(
            "deployments resolved repository=%s provider=%d configured=%d",
            full_name, provider_deployments, derived,
        )

        # Runtime and incident providers are optional. A provider that is not
        # configured contributes nothing and is not an error; coverage reports
        # the absence rather than the sync failing.
        if prometheus.is_configured():
            prometheus.sync_runtime_observations(db, repo)
        if pagerduty.is_configured():
            pagerduty.sync_incidents(db, repo)

        job.status = SyncStatus.SUCCESS
        logger.info(
            "sync succeeded repository=%s pull_requests=%d workflow_runs=%d",
            full_name, job.pull_requests_written, job.workflow_runs_written,
        )
    except ConnectorError as error:
        # Whatever was already committed stays. If some records landed before the
        # failure the sync is PARTIAL, not FAILED, because the difference decides
        # whether the data behind a metric can be trusted.
        wrote_anything = (job.pull_requests_written or 0) + (job.workflow_runs_written or 0) > 0
        job.status = SyncStatus.PARTIAL if wrote_anything else SyncStatus.FAILED
        job.error_code = error.code.value
        job.error_message = error.message
        logger.error("sync %s repository=%s code=%s: %s", job.status.lower(), full_name, error.code.value, error.message)
    finally:
        job.finished_at = utc_now()
        db.commit()

    return job


def sync_all() -> list[SyncJob]:
    """Sync every repository in GITHUB_REPOS.

    One repository failing does not abort the others; each records its own
    outcome so partial coverage is visible rather than hidden.
    """
    db = SessionLocal()
    try:
        if not settings.github_token:
            job = SyncJob(
                provider="github",
                status=SyncStatus.FAILED,
                started_at=utc_now(),
                finished_at=utc_now(),
                error_code=ErrorCode.CONFIGURATION_ERROR.value,
                error_message="GITHUB_TOKEN is not set. Add it to backend/.env.",
            )
            db.add(job)
            db.commit()
            logger.error("sync aborted: GITHUB_TOKEN is not set")
            return [job]

        if not settings.repo_list:
            job = SyncJob(
                provider="github",
                status=SyncStatus.FAILED,
                started_at=utc_now(),
                finished_at=utc_now(),
                error_code=ErrorCode.CONFIGURATION_ERROR.value,
                error_message="GITHUB_REPOS is empty. Nothing to sync.",
            )
            db.add(job)
            db.commit()
            logger.error("sync aborted: GITHUB_REPOS is empty")
            return [job]

        jobs: list[SyncJob] = []
        with httpx.Client(headers=_headers(), timeout=30.0, follow_redirects=True) as client:
            for full_name in settings.repo_list:
                jobs.append(sync_repository(db, full_name, client))
        return jobs
    finally:
        db.close()


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging()
    sync_all()
