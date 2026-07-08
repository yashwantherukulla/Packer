"""baseline: jobs, models, artifacts, reports

Revision ID: 0001
Revises:
Create Date: 2026-07-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("input_ref", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("result_ref", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("progress_step", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_jobs_input_hash", "jobs", ["input_hash"])

    op.create_table(
        "models",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_models_sha256", "models", ["sha256"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
        ),
        sa.Column("pak_path", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_job_id", "artifacts", ["job_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reports_job_id", "reports", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_job_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_artifacts_job_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_models_sha256", table_name="models")
    op.drop_table("models")
    op.drop_index("ix_jobs_input_hash", table_name="jobs")
    op.drop_table("jobs")
