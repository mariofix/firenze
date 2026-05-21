"""auth_login_code_passwordless

Revision ID: c1b2a3d4e5f7
Revises: a8c5e1f2b9d3, 66cf5b9778fd
Create Date: 2026-05-13 22:20:00.000000-04:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c1b2a3d4e5f7"
down_revision = ("a8c5e1f2b9d3", "66cf5b9778fd")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_code",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("requested_ua", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_login_code_user_id", "auth_login_code", ["user_id"], unique=False)
    op.create_index("ix_auth_login_code_expires_at", "auth_login_code", ["expires_at"], unique=False)
    op.create_index("ix_auth_login_code_consumed_at", "auth_login_code", ["consumed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_login_code_consumed_at", table_name="auth_login_code")
    op.drop_index("ix_auth_login_code_expires_at", table_name="auth_login_code")
    op.drop_index("ix_auth_login_code_user_id", table_name="auth_login_code")
    op.drop_table("auth_login_code")
