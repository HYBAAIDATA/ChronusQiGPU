"""Initial schema for Chronus enterprise production execution fabric

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-07 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. workloads table
    op.create_table(
        'workloads',
        sa.Column('workload_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('response_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('workload_id')
    )
    op.create_index('ix_workloads_tenant_id', 'workloads', ['tenant_id'], unique=False)
    op.create_index('ix_workloads_status', 'workloads', ['status'], unique=False)
    op.create_index('ix_workloads_tenant_status', 'workloads', ['tenant_id', 'status'], unique=False)

    # 2. execution_records table
    op.create_table(
        'execution_records',
        sa.Column('record_id', sa.String(length=64), nullable=False),
        sa.Column('workload_id', sa.String(length=64), nullable=False),
        sa.Column('backend', sa.String(length=64), nullable=False),
        sa.Column('execution_mode', sa.String(length=64), nullable=False),
        sa.Column('duration_ms', sa.Float(), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('record_id')
    )
    op.create_index('ix_execution_records_workload', 'execution_records', ['workload_id'], unique=False)

    # 3. receipts table
    op.create_table(
        'receipts',
        sa.Column('receipt_id', sa.String(length=64), nullable=False),
        sa.Column('workload_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('signature', sa.Text(), nullable=False),
        sa.Column('algorithm', sa.String(length=32), nullable=False),
        sa.Column('verified', sa.Integer(), nullable=True),
        sa.Column('receipt_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('receipt_id')
    )
    op.create_index('ix_receipts_tenant_workload', 'receipts', ['tenant_id', 'workload_id'], unique=False)

    # 4. tenant_usage_metrics table
    op.create_table(
        'tenant_usage_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('ccu_consumed', sa.Float(), nullable=True),
        sa.Column('requests_total', sa.Integer(), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenant_usage_metrics_tenant_id', 'tenant_usage_metrics', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tenant_usage_metrics_tenant_id', table_name='tenant_usage_metrics')
    op.drop_table('tenant_usage_metrics')
    op.drop_index('ix_receipts_tenant_workload', table_name='receipts')
    op.drop_table('receipts')
    op.drop_index('ix_execution_records_workload', table_name='execution_records')
    op.drop_table('execution_records')
    op.drop_index('ix_workloads_tenant_status', table_name='workloads')
    op.drop_index('ix_workloads_status', table_name='workloads')
    op.drop_index('ix_workloads_tenant_id', table_name='workloads')
    op.drop_table('workloads')
