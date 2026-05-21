"""add api_credential table

Revision ID: d5e6f7a8b9c0
Revises: c1b2a3d4e5f7
Create Date: 2026-05-14 22:15:00.000000-04:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "c1b2a3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_credential",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("api_key", sa.String(length=96), nullable=False),
        sa.Column("api_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_credential_user_id", "api_credential", ["user_id"], unique=False)
    op.create_index("ix_api_credential_api_key", "api_credential", ["api_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_credential_api_key", table_name="api_credential")
    op.drop_index("ix_api_credential_user_id", table_name="api_credential")
    op.drop_table("api_credential")
