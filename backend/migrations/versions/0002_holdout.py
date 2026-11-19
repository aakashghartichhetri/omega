"""Add holdout evaluation and per-case ratios without losing existing runs.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Server default keeps rows from the original MVP valid during migration.
    op.add_column("runs", sa.Column("holdout_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("runs", sa.Column("holdout_digest", sa.String(64), nullable=True))
    op.add_column("runs", sa.Column("holdout_workloads", sa.JSON(), nullable=True))
    op.add_column("runs", sa.Column("winner_holdout_ratio", sa.Float(), nullable=True))
    op.add_column("candidates", sa.Column("train_case_ratios", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("holdout_case_ratios", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("holdout_average_ratio", sa.Float(), nullable=True))
    op.add_column("candidates", sa.Column("holdout_worst_ratio", sa.Float(), nullable=True))


def downgrade():
    # Batch operations also support the SQLite migration smoke test.
    with op.batch_alter_table("candidates") as batch:
        for name in ("holdout_worst_ratio", "holdout_average_ratio", "holdout_case_ratios", "train_case_ratios"):
            batch.drop_column(name)
    with op.batch_alter_table("runs") as batch:
        for name in ("winner_holdout_ratio", "holdout_workloads", "holdout_digest", "holdout_count"):
            batch.drop_column(name)
