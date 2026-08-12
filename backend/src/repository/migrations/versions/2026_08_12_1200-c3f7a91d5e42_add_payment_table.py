"""add payment table for ApiPay.kz (Kaspi Pay) invoices

Revision ID: c3f7a91d5e42
Revises: 7b8e1bbfdf3f
Create Date: 2026-08-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3f7a91d5e42'
down_revision = '7b8e1bbfdf3f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_order_id', sa.String(length=64), nullable=False),
        sa.Column('apipay_invoice_id', sa.BigInteger(), nullable=True),
        # Intentionally not a FK: the authoritative booking rows live in the bot service.
        sa.Column('booking_id', sa.Integer(), nullable=True),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('phone', sa.String(length=16), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('refunded_amount', sa.Numeric(precision=12, scale=2), server_default=sa.text('0'), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bot_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bot_notify_error', sa.Text(), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['account.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_order_id'),
        sa.UniqueConstraint('apipay_invoice_id'),
    )
    op.create_index(op.f('ix_payment_external_order_id'), 'payment', ['external_order_id'], unique=False)
    op.create_index(op.f('ix_payment_apipay_invoice_id'), 'payment', ['apipay_invoice_id'], unique=False)
    op.create_index(op.f('ix_payment_booking_id'), 'payment', ['booking_id'], unique=False)
    op.create_index(op.f('ix_payment_status'), 'payment', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_status'), table_name='payment')
    op.drop_index(op.f('ix_payment_booking_id'), table_name='payment')
    op.drop_index(op.f('ix_payment_apipay_invoice_id'), table_name='payment')
    op.drop_index(op.f('ix_payment_external_order_id'), table_name='payment')
    op.drop_table('payment')
