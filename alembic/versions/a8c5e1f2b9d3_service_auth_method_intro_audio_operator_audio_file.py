"""service auth_method intro_audio operator audio_file

Revision ID: a8c5e1f2b9d3
Revises: 124ca3374fe3
Create Date: 2026-03-22 00:00:00.000000-03:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a8c5e1f2b9d3"
down_revision = "124ca3374fe3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service", sa.Column("auth_method", sa.String(length=8), nullable=False, server_default="ani"))
    op.add_column("service", sa.Column("intro_audio", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("operator", sa.Column("audio_file", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("operator", "audio_file")
    op.drop_column("service", "intro_audio")
    op.drop_column("service", "auth_method")
