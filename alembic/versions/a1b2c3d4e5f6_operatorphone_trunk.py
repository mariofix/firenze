"""operatorphone: add trunk column

Revision ID: a1b2c3d4e5f6
Revises: 3d332fe36da6
Create Date: 2026-03-16 00:00:00.000000-04:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "3d332fe36da6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "operator_phone",
        sa.Column("trunk", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("operator_phone", "trunk")
