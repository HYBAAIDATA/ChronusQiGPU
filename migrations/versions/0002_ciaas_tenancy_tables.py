"""Add CIaaS tenancy tables declared in chronus.service.postgres_store

Revision ID: 0002_ciaas_tenancy_tables
Revises: 0001_initial_schema
Create Date: 2026-11-18 23:50:00.000000

``postgres_store.metadata`` (the alembic ``target_metadata``) declares
``ciaas_tenants`` and ``ciaas_capacity_ledger`` but 0001 never created them,
so a database provisioned with ``alembic upgrade head`` lacked tables the
CIaaS onboarding/capacity paths write to. This revision closes that gap.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_ciaas_tenancy_tables'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ciaas_tenants',
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('contract_id', sa.String(length=128), nullable=False),
        sa.Column('company_name', sa.String(length=256), nullable=False),
        sa.Column('admin_email', sa.String(length=256), nullable=False),
        sa.Column('assigned_cce_id', sa.String(length=128), nullable=False),
        sa.Column('schema_name', sa.String(length=128), nullable=False),
        sa.Column('enduring_addendum_accepted', sa.Boolean(), nullable=False),
        sa.Column('active_warps', sa.Integer(), nullable=False),
        sa.Column('max_authorized_warps', sa.Integer(), nullable=False),
        sa.Column('data_at_rest_gb', sa.Integer(), nullable=False),
        sa.Column('data_in_motion_gb', sa.Integer(), nullable=False),
        sa.Column('kms_provider', sa.String(length=64), nullable=False),
        sa.Column('kms_key_arn', sa.Text(), nullable=False),
        sa.Column('profile_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('tenant_id'),
        sa.UniqueConstraint('assigned_cce_id'),
    )
    op.create_index('ix_ciaas_tenants_contract_id', 'ciaas_tenants', ['contract_id'], unique=False)

    op.create_table(
        'ciaas_capacity_ledger',
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=128), nullable=False),
        sa.Column('previous_warps', sa.Integer(), nullable=False),
        sa.Column('new_active_warps', sa.Integer(), nullable=False),
        sa.Column('previous_storage_gb', sa.Integer(), nullable=False),
        sa.Column('new_storage_gb', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index('ix_ciaas_capacity_ledger_tenant_id', 'ciaas_capacity_ledger', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ciaas_capacity_ledger_tenant_id', table_name='ciaas_capacity_ledger')
    op.drop_table('ciaas_capacity_ledger')
    op.drop_index('ix_ciaas_tenants_contract_id', table_name='ciaas_tenants')
    op.drop_table('ciaas_tenants')
