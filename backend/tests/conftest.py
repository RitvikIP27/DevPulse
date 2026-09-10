"""Shared test fixtures.

Unit and API tests run against in-memory SQLite. The MVP models use only generic
column types, so this is faithful enough and keeps the suite fast (testing.md 2:
use the cheapest reliable level first). Tests that depend on real PostgreSQL
behaviour — JSON containment, migration correctness, concurrent upserts — belong
in a separate integration suite against a live database (testing.md 4).

Note that tables here are created from ``Base.metadata``, not by running
migrations. Migrations are verified separately against PostgreSQL, because
SQLite cannot represent every operation a migration may perform.
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.events import PullRequest, Repository, WorkflowRun

# The metrics engine derives its look-back window from the wall clock, so test
# events must be positioned relative to the same instant or they would drift out
# of the window as real time passes. Captured once at import: every test in a run
# shares one reference point, and each test expresses timings as offsets from it.
#
# Naive UTC, because the MVP stores naive datetimes. Moving the schema to
# timezone-aware timestamps is Finding 14 and changes this line deliberately.
NOW = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Neutralise ambient configuration for every test.

    Settings are loaded from backend/.env, so a developer with DEMO_MODE or a
    PROMETHEUS_URL set would silently change what the suite asserts — and it did:
    five provider-availability tests passed in CI and failed locally purely
    because a local .env enabled demo mode.

    A test that depends on the machine it runs on is not a test. Anything that
    needs a provider switched on turns it on explicitly.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "demo_mode", False, raising=False)
    monkeypatch.setattr(settings, "prometheus_url", "", raising=False)
    monkeypatch.setattr(settings, "pagerduty_token", "", raising=False)
    monkeypatch.setattr(settings, "pagerduty_service_ids", "", raising=False)
    monkeypatch.setattr(settings, "github_token", "test-token", raising=False)


@pytest.fixture
def db_session() -> Session:
    """A clean in-memory database per test.

    StaticPool keeps every connection pointed at the same in-memory database;
    without it SQLite would hand out a fresh empty database per connection.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(db_session: Session) -> TestClient:
    """TestClient wired to the test database instead of the real one."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def repository(db_session: Session) -> Repository:
    repo = Repository(full_name="devpulse-test/payments-api", display_name="payments")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


class RunBuilder:
    """Creates workflow runs positioned relative to NOW.

    Offsets are expressed in minutes before NOW so that tests read as a timeline
    rather than as a list of absolute timestamps.
    """

    # github_run_id is globally unique, not unique per repository, so ids are
    # drawn from one counter shared across every builder in the process.
    _run_ids = itertools.count(1)

    def __init__(self, session: Session, repository: Repository):
        self._session = session
        self._repository = repository

    def add(
        self,
        *,
        workflow_name: str = "CI",
        conclusion: str | None = "success",
        started_minutes_ago: float = 60.0,
        duration_minutes: float | None = 5.0,
    ) -> WorkflowRun:
        started_at = NOW - timedelta(minutes=started_minutes_ago)
        completed_at = (
            started_at + timedelta(minutes=duration_minutes)
            if duration_minutes is not None
            else None
        )
        run = WorkflowRun(
            repository_id=self._repository.id,
            github_run_id=f"run-{next(self._run_ids)}",
            workflow_name=workflow_name,
            conclusion=conclusion,
            started_at=started_at,
            completed_at=completed_at,
        )
        self._session.add(run)
        self._session.commit()
        return run

    def add_merged_pr(
        self, *, number: int, merged_minutes_ago: float, opened_minutes_ago: float = 600.0
    ) -> PullRequest:
        pr = PullRequest(
            repository_id=self._repository.id,
            github_pr_number=number,
            title=f"PR #{number}",
            opened_at=NOW - timedelta(minutes=opened_minutes_ago),
            merged_at=NOW - timedelta(minutes=merged_minutes_ago),
            is_merged=True,
        )
        self._session.add(pr)
        self._session.commit()
        return pr


@pytest.fixture
def runs(db_session: Session, repository: Repository) -> RunBuilder:
    return RunBuilder(db_session, repository)
