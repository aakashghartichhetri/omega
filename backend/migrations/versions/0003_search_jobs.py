"""Persist asynchronous experiments without changing historical runs.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "search_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_search_jobs_status", "search_jobs", ["status"])


def downgrade():
    op.drop_index("ix_search_jobs_status", table_name="search_jobs")
    op.drop_table("search_jobs")
