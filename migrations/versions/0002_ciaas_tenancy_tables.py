"""Add CIaaS tenancy tables declared in chronus.service.postgres_store

Revision ID: 0002_ciaas_tenancy_tables
Revises: 0001_initial_schema
Create Date: 2026-11-18 23:50:00.000000

``postgres_store.metadata`` (the alembic ``target_metadata``) declares
``ciaas_tenants`` and ``ciaas_capacity_ledger`` but 0001 never created them,
so a database provisioned with ``alembic upgrade head`` lacked tables the
CIaaS onboarding/capacity paths write to. This revision closes that gap.

Deployments stamped at 0001 may already have these tables because
``PostgresWorkloadStore.init_db()`` runs ``metadata.create_all``; existing
tables and indexes are therefore kept (never dropped or recreated).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_ciaas_tenancy_tables'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _offline() -> bool:
    # ``alembic upgrade --sql`` has no live connection to inspect; emit plain DDL.
    return op.get_context().as_sql


def _existing_tables() -> set:
    if _offline():
        return set()
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_indexes(table: str) -> set:
    if _offline() or table not in _existing_tables():
        return set()
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _existing_tables()
    if 'ciaas_tenants' not in tables:
        _create_ciaas_tenants()
    if 'ix_ciaas_tenants_contract_id' not in _existing_indexes('ciaas_tenants'):
        op.create_index('ix_ciaas_tenants_contract_id', 'ciaas_tenants', ['contract_id'], unique=False)
    if 'ciaas_capacity_ledger' not in tables:
        _create_ciaas_capacity_ledger()
    if 'ix_ciaas_capacity_ledger_tenant_id' not in _existing_indexes('ciaas_capacity_ledger'):
        op.create_index('ix_ciaas_capacity_ledger_tenant_id', 'ciaas_capacity_ledger', ['tenant_id'], unique=False)


def _create_ciaas_tenants() -> None:
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


def _create_ciaas_capacity_ledger() -> None:
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


def downgrade() -> None:
    op.drop_index('ix_ciaas_capacity_ledger_tenant_id', table_name='ciaas_capacity_ledger')
    op.drop_table('ciaas_capacity_ledger')
    op.drop_index('ix_ciaas_tenants_contract_id', table_name='ciaas_tenants')
    op.drop_table('ciaas_tenants')
