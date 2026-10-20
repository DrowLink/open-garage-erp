"""Add a role to shop-scoped users.

Revision ID: 0004_user_roles
Revises: 0003_session_tokens
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_roles"
down_revision: str | None = "0003_session_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=True),
    )
    users = sa.table("users", sa.column("role", sa.String(length=32)))
    op.execute(users.update().where(users.c.role.is_(None)).values(role="owner"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_users_role",
            "role IN ('owner', 'service_advisor', 'technician', 'accountant')",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.drop_column("role")
