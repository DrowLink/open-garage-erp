"""Add non-destructive customer archival.

Revision ID: 0007_customer_archive
Revises: 0006_parent_lookup_indexes
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_customer_archive"
down_revision: str | None = "0006_parent_lookup_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "archived_at")
