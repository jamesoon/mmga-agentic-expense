"""add user_justification to claims

Revision ID: 010
Revises: 009
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("user_justification", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("claims", "user_justification")
