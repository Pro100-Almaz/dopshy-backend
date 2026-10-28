"""booking prefill

Revision ID: a41f7c2d9e10
Revises: cf27c884b30d
Create Date: 2026-10-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a41f7c2d9e10'
down_revision = 'cf27c884b30d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('booking_prefill',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('customer_name', sa.String(length=128), nullable=True),
    sa.Column('field_id', sa.SmallInteger(), nullable=True),
    sa.Column('date', sa.Date(), nullable=True),
    sa.Column('time_start', sa.Time(), nullable=True),
    sa.Column('time_end', sa.Time(), nullable=True),
    sa.Column('players', sa.SmallInteger(), nullable=True),
    sa.Column('lang', sa.String(length=2), nullable=True),
    sa.Column('source', sa.String(length=32), server_default='bot_link', nullable=False),
    sa.Column('conversation_id', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('first_opened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('bot_booking_ids', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_booking_prefill_token_hash'), 'booking_prefill', ['token_hash'], unique=True)
    op.create_index(op.f('ix_booking_prefill_expires_at'), 'booking_prefill', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_booking_prefill_expires_at'), table_name='booking_prefill')
    op.drop_index(op.f('ix_booking_prefill_token_hash'), table_name='booking_prefill')
    op.drop_table('booking_prefill')
