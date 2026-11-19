"""Create search runs and scored candidates.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("machines", sa.Integer(), nullable=False),
        sa.Column("job_count", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("candidate_limit", sa.Integer(), nullable=False),
        sa.Column("workload_digest", sa.String(64), nullable=False),
        sa.Column("workloads", sa.JSON(), nullable=False),
        sa.Column("winner_ordinal", sa.Integer(), nullable=False),
        sa.Column("winner_ratio", sa.Float(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("ordering", sa.String(24), nullable=False),
        sa.Column("order_parameter", sa.Integer(), nullable=False),
        sa.Column("placement", sa.String(24), nullable=False),
        sa.Column("placement_seed", sa.Integer(), nullable=False),
        sa.Column("passes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("average_ratio", sa.Float(), nullable=True),
        sa.Column("worst_ratio", sa.Float(), nullable=True),
        sa.Column("mean_makespan", sa.Float(), nullable=True),
        sa.Column("preview_assignments", sa.JSON(), nullable=True),
        sa.Column("preview_makespan", sa.Integer(), nullable=True),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_candidates_run_ordinal"),
    )
    op.create_index("ix_candidates_run_id", "candidates", ["run_id"])
    op.create_index("ix_candidates_status", "candidates", ["status"])


def downgrade():
    op.drop_index("ix_candidates_status", table_name="candidates")
    op.drop_index("ix_candidates_run_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("runs")
