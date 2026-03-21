"""unified client model

Revision ID: f479283e23a2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-17 16:14:00.751587-03:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f479283e23a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('client',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('pin', sa.String(length=8), nullable=True),
    sa.Column('ani', sa.String(length=16), nullable=True),
    sa.Column('full_name', sa.String(length=128), nullable=True),
    sa.Column('email', sa.String(length=512), nullable=True),
    sa.Column('phone_number', sa.String(length=16), nullable=True),
    sa.Column('credits', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('modified_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['service_id'], ['service.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('service_id', 'client_id', name='uq_client_service_clientid')
    )
    op.create_index('ix_client_pin', 'client', ['service_id', 'pin'], unique=False)
    op.create_index('ix_client_ani', 'client', ['service_id', 'ani'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_client_ani', table_name='client')
    op.drop_index('ix_client_pin', table_name='client')
    op.drop_table('client')
