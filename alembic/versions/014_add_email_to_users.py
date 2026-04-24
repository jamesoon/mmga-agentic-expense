"""add email column to users table

Revision ID: 014
Revises: 013
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email")
