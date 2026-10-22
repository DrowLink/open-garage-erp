"""Index vehicle and repair-order parent lookups.

Revision ID: 0006_parent_lookup_indexes
Revises: 0005_auth_rate_limits
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_parent_lookup_indexes"
down_revision: str | None = "0005_auth_rate_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_vehicles_customer_id", "vehicles", ["customer_id"], unique=False)
    op.create_index(
        "ix_repair_orders_vehicle_id", "repair_orders", ["vehicle_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_repair_orders_vehicle_id", table_name="repair_orders")
    op.drop_index("ix_vehicles_customer_id", table_name="vehicles")
