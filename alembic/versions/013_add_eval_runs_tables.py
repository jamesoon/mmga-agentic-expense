"""add eval_runs and eval_judgments tables

Revision ID: 013
Revises: 012
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=False),
        sa.Column("judge_model", sa.String(length=100), nullable=False),
        sa.Column("verifier_model", sa.String(length=100), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("results_path", sa.String(length=500), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("triggered_by", sa.String(length=200), nullable=False),
    )
    op.create_index("ix_eval_runs_started_at", "eval_runs", ["started_at"])

    op.create_table(
        "eval_judgments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_id", sa.String(length=20), nullable=False),
        sa.Column("pipeline", sa.String(length=30), nullable=False),
        sa.Column("self_consistency_runs", postgresql.JSONB(), nullable=False),
        sa.Column("consistency_score", sa.Float(), nullable=False),
        sa.Column("cross_modal_verdict", sa.String(length=40), nullable=True),
        sa.Column("cross_modal_agree", sa.Boolean(), nullable=True),
        sa.Column("primary_judge_score", sa.Float(), nullable=False),
        sa.Column("verifier_judge_score", sa.Float(), nullable=False),
        sa.Column("verifier_agree", sa.Boolean(), nullable=False),
        sa.Column("disagreement_score", sa.Float(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("reasoning_digest", sa.Text(), nullable=True),
    )
    op.create_index("ix_eval_judgments_run_id", "eval_judgments", ["run_id"])
    op.create_index("ix_eval_judgments_benchmark_id", "eval_judgments", ["benchmark_id"])
    op.create_index("ix_eval_judgments_pipeline", "eval_judgments", ["pipeline"])
    op.create_index(
        "ix_eval_judgments_disagreement_desc",
        "eval_judgments",
        ["disagreement_score"],
        postgresql_ops={"disagreement_score": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_eval_judgments_disagreement_desc", table_name="eval_judgments")
    op.drop_index("ix_eval_judgments_pipeline", table_name="eval_judgments")
    op.drop_index("ix_eval_judgments_benchmark_id", table_name="eval_judgments")
    op.drop_index("ix_eval_judgments_run_id", table_name="eval_judgments")
    op.drop_table("eval_judgments")
    op.drop_index("ix_eval_runs_started_at", table_name="eval_runs")
    op.drop_table("eval_runs")
