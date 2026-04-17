"""add user_quota_usage table

Revision ID: 011
Revises: 010
Create Date: 2026-04-17

"""
from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_quota_usage",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("date", sa.Date(), primary_key=True, nullable=False),
        sa.Column("submissions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("user_quota_usage")
