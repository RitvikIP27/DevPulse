"""Baseline schema: the MVP tables as they exist today.

Revision ID: 0001_baseline
Revises: None
Create Date: 2026-09-10

This migration is a faithful snapshot of the schema that
``Base.metadata.create_all`` produced during the MVP phase. It exists so that
every subsequent schema change has migration history to build on (rules.md 13),
and so the startup-time create_all can be removed from app.main.

Existing-database safety
------------------------
Development and demo databases already contain these three tables, created by
create_all before migrations existed — including the volume holding the Stage 0
audit fixture (21 PRs / 90 workflow runs), which is deliberately preserved.
Running a plain CREATE TABLE against those databases would abort the upgrade, so
each table is created only when absent. The alternative, asking every existing
environment to run ``alembic stamp head`` by hand, cannot be automated in the
container entrypoint and would silently diverge for anyone who forgot.

This guard is specific to the baseline. Later migrations describe real deltas and
must not copy this pattern.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "repositories" not in existing:
        op.create_table(
            "repositories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_repositories_id", "repositories", ["id"])
        op.create_index(
            "ix_repositories_full_name", "repositories", ["full_name"], unique=True
        )

    if "pull_requests" not in existing:
        op.create_table(
            "pull_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("repository_id", sa.Integer(), nullable=False),
            sa.Column("github_pr_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("merged_at", sa.DateTime(), nullable=True),
            sa.Column("is_merged", sa.Boolean(), nullable=True),
            sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pull_requests_id", "pull_requests", ["id"])

    if "workflow_runs" not in existing:
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("repository_id", sa.Integer(), nullable=False),
            sa.Column("github_run_id", sa.String(), nullable=False),
            sa.Column("workflow_name", sa.String(), nullable=False),
            sa.Column("conclusion", sa.String(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("github_run_id"),
        )
        op.create_index("ix_workflow_runs_id", "workflow_runs", ["id"])


def downgrade() -> None:
    op.drop_table("workflow_runs")
    op.drop_table("pull_requests")
    op.drop_table("repositories")
