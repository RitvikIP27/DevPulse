"""GitHub connector tests.

Uses respx so no test touches the network (testing.md 10). The failure paths
matter most here: the audit proved a 401 could vanish entirely, leaving a metric
built on partial data with nothing to indicate it.
"""

import httpx
import pytest
import respx

from app.models.events import PullRequest, SyncJob, WorkflowRun
from app.services.errors import ErrorCode
from app.services.github_client import (
    GITHUB_API,
    SyncStatus,
    sync_pull_requests,
    sync_repository,
    sync_workflow_runs,
)

PULLS_URL = f"{GITHUB_API}/repos/devpulse-test/payments-api/pulls"
RUNS_URL = f"{GITHUB_API}/repos/devpulse-test/payments-api/actions/runs"

PR_PAYLOAD = {
    "number": 482,
    "title": "Fix payment validation",
    "created_at": "2026-07-09T09:12:00Z",
    "merged_at": "2026-07-09T14:32:00Z",
    "closed_at": "2026-07-09T14:32:00Z",
    "merge_commit_sha": "abc123def456",
    "head": {"sha": "head789", "ref": "fix/payment-validation"},
    "base": {"ref": "main"},
    "user": {"login": "octocat"},
    "html_url": "https://github.com/devpulse-test/payments-api/pull/482",
}

RUN_PAYLOAD = {
    "id": 18291,
    "name": "Deploy to production",
    "status": "completed",
    "conclusion": "success",
    "run_started_at": "2026-07-09T14:45:00Z",
    "updated_at": "2026-07-09T14:48:00Z",
    "head_sha": "abc123def456",
    "head_branch": "main",
    "event": "push",
    "run_attempt": 1,
    "html_url": "https://github.com/devpulse-test/payments-api/actions/runs/18291",
}


@pytest.fixture
def client():
    with httpx.Client(base_url="") as http_client:
        yield http_client


@respx.mock
def test_pull_request_ingestion_captures_the_correlation_keys(db_session, repository, client):
    respx.get(PULLS_URL).mock(return_value=httpx.Response(200, json=[PR_PAYLOAD]))

    written = sync_pull_requests(db_session, repository, client)

    assert written == 1
    pr = db_session.query(PullRequest).one()
    # merge_commit_sha is the commit that landed, and therefore what a later
    # deployment will report shipping. Without it nothing can be correlated.
    assert pr.merge_commit_sha == "abc123def456"
    assert pr.head_sha == "head789"
    assert pr.base_branch == "main"
    assert pr.head_branch == "fix/payment-validation"
    assert pr.author_login == "octocat"
    assert pr.is_merged is True


@respx.mock
def test_workflow_run_ingestion_captures_the_correlation_keys(db_session, repository, client):
    respx.get(RUNS_URL).mock(return_value=httpx.Response(200, json={"workflow_runs": [RUN_PAYLOAD]}))

    written = sync_workflow_runs(db_session, repository, client)

    assert written == 1
    run = db_session.query(WorkflowRun).one()
    assert run.head_sha == "abc123def456"
    assert run.head_branch == "main"
    assert run.event == "push"
    assert run.status == "completed"


@respx.mock
def test_a_run_and_the_pull_request_it_shipped_share_a_commit(db_session, repository, client):
    """The whole point of Stage 2: these two records can now be joined."""
    respx.get(PULLS_URL).mock(return_value=httpx.Response(200, json=[PR_PAYLOAD]))
    respx.get(RUNS_URL).mock(return_value=httpx.Response(200, json={"workflow_runs": [RUN_PAYLOAD]}))

    sync_pull_requests(db_session, repository, client)
    sync_workflow_runs(db_session, repository, client)

    pr = db_session.query(PullRequest).one()
    run = db_session.query(WorkflowRun).one()
    assert pr.merge_commit_sha == run.head_sha


@respx.mock
def test_an_in_progress_run_has_no_completion_timestamp(db_session, repository, client):
    running = {**RUN_PAYLOAD, "status": "in_progress", "conclusion": None}
    respx.get(RUNS_URL).mock(return_value=httpx.Response(200, json={"workflow_runs": [running]}))

    sync_workflow_runs(db_session, repository, client)

    assert db_session.query(WorkflowRun).one().completed_at is None


@respx.mock
def test_a_run_without_a_parseable_start_time_is_skipped_not_stored_with_a_guess(
    db_session, repository, client
):
    """started_at is NOT NULL. Inventing one would corrupt every duration."""
    broken = {**RUN_PAYLOAD, "run_started_at": None, "created_at": None}
    respx.get(RUNS_URL).mock(return_value=httpx.Response(200, json={"workflow_runs": [broken]}))

    assert sync_workflow_runs(db_session, repository, client) == 0
    assert db_session.query(WorkflowRun).count() == 0


@respx.mock
def test_resyncing_updates_rather_than_duplicates(db_session, repository, client):
    respx.get(PULLS_URL).mock(return_value=httpx.Response(200, json=[PR_PAYLOAD]))
    sync_pull_requests(db_session, repository, client)

    respx.get(PULLS_URL).mock(
        return_value=httpx.Response(200, json=[{**PR_PAYLOAD, "title": "Renamed"}])
    )
    sync_pull_requests(db_session, repository, client)

    assert db_session.query(PullRequest).count() == 1
    assert db_session.query(PullRequest).one().title == "Renamed"


@respx.mock
def test_pagination_follows_the_link_header(db_session, repository, client):
    page_two = f"{PULLS_URL}?page=2"

    # One route serving both pages, keyed on the query string. Registering two
    # routes would not work: a route for the bare path also matches the
    # paginated URL, so page two would silently replay page one.
    def paginated(request: httpx.Request) -> httpx.Response:
        if "page=2" in str(request.url):
            return httpx.Response(200, json=[{**PR_PAYLOAD, "number": 483}])
        return httpx.Response(
            200, json=[PR_PAYLOAD], headers={"Link": f'<{page_two}>; rel="next"'}
        )

    respx.get(url__startswith=PULLS_URL).mock(side_effect=paginated)

    written = sync_pull_requests(db_session, repository, client)

    assert written == 2
    assert {pr.github_pr_number for pr in db_session.query(PullRequest).all()} == {482, 483}


@respx.mock
def test_pagination_stops_when_the_rate_limit_reserve_is_reached(db_session, repository, client):
    """Draining the quota entirely would break unrelated interactive requests."""
    respx.get(PULLS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[PR_PAYLOAD],
            headers={
                "Link": f'<{PULLS_URL}?page=2>; rel="next"',
                "x-ratelimit-remaining": "3",
            },
        )
    )

    assert sync_pull_requests(db_session, repository, client) == 1


@respx.mock
def test_an_authentication_failure_is_recorded_instead_of_disappearing(db_session, repository):
    """Audit finding 4. This exact scenario previously produced no trace at all."""
    respx.get(PULLS_URL).mock(return_value=httpx.Response(401, json={"message": "Bad credentials"}))

    with httpx.Client() as http_client:
        job = sync_repository(db_session, "devpulse-test/payments-api", http_client)

    assert job.status == SyncStatus.FAILED
    assert job.error_code == ErrorCode.AUTHENTICATION_ERROR.value
    assert "GITHUB_TOKEN" in job.error_message
    assert job.finished_at is not None
    assert db_session.query(SyncJob).count() == 1


@respx.mock
def test_a_failure_after_partial_progress_is_partial_not_failed(db_session, repository):
    """The distinction decides whether a metric's data can be trusted."""
    respx.get(PULLS_URL).mock(return_value=httpx.Response(200, json=[PR_PAYLOAD]))
    respx.get(RUNS_URL).mock(return_value=httpx.Response(500, json={"message": "boom"}))

    with httpx.Client() as http_client:
        job = sync_repository(db_session, "devpulse-test/payments-api", http_client)

    assert job.status == SyncStatus.PARTIAL
    assert job.pull_requests_written == 1
    assert job.error_code == ErrorCode.PROVIDER_ERROR.value


@respx.mock
def test_a_successful_sync_records_what_it_wrote(db_session, repository):
    respx.get(PULLS_URL).mock(return_value=httpx.Response(200, json=[PR_PAYLOAD]))
    respx.get(RUNS_URL).mock(return_value=httpx.Response(200, json={"workflow_runs": [RUN_PAYLOAD]}))

    with httpx.Client() as http_client:
        job = sync_repository(db_session, "devpulse-test/payments-api", http_client)

    assert job.status == SyncStatus.SUCCESS
    assert job.pull_requests_written == 1
    assert job.workflow_runs_written == 1
    assert job.error_code is None
