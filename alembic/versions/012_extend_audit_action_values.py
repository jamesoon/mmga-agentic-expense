"""audit_log.action already free-text — no schema change needed

Revision ID: 012
Revises: 011
Create Date: 2026-04-17

This migration is an intentional no-op: the audit_log.action column is
free-text (String/Text/VARCHAR), so it already accepts all Spec A
boundary-trip values without schema change. The migration is recorded
to keep the Alembic chain linear.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentional no-op — column is already free-text
    pass


def downgrade() -> None:
    # Intentional no-op
    pass
