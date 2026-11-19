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
tables and indexes are therefore kept (never dropped or recreated): DDL is
``CREATE ... IF NOT EXISTS`` both online and in offline ``--sql`` output.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_ciaas_tenancy_tables'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_meta = sa.MetaData()

ciaas_tenants = sa.Table(
    'ciaas_tenants',
    _meta,
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

ciaas_capacity_ledger = sa.Table(
    'ciaas_capacity_ledger',
    _meta,
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

_indexes = (
    sa.Index('ix_ciaas_tenants_contract_id', ciaas_tenants.c.contract_id),
    sa.Index('ix_ciaas_capacity_ledger_tenant_id', ciaas_capacity_ledger.c.tenant_id),
)


def upgrade() -> None:
    for table in (ciaas_tenants, ciaas_capacity_ledger):
        op.execute(sa.schema.CreateTable(table, if_not_exists=True))
    for index in _indexes:
        op.execute(sa.schema.CreateIndex(index, if_not_exists=True))


def downgrade() -> None:
    # The tables may predate this revision (runtime ``create_all``), so never
    # silently drop tenant data: refuse when rows exist. Offline ``--sql``
    # output emits the DROPs for the operator to review.
    if not op.get_context().as_sql:
        bind = op.get_bind()
        existing = set(sa.inspect(bind).get_table_names())
        if bind.dialect.name == "postgresql":
            # Hold writers off between the emptiness check and the DROP
            # (released at the end of the migration transaction).
            for table in (ciaas_capacity_ledger, ciaas_tenants):
                if table.name in existing:
                    op.execute(sa.text(f'LOCK TABLE "{table.name}" IN ACCESS EXCLUSIVE MODE'))
        for table in (ciaas_capacity_ledger, ciaas_tenants):
            if table.name in existing and bind.execute(
                sa.select(sa.func.count()).select_from(table)
            ).scalar_one():
                raise RuntimeError(
                    f"refusing to downgrade 0002: {table.name} contains rows; "
                    "export or remove them explicitly first"
                )
    op.execute(sa.text("DROP INDEX IF EXISTS ix_ciaas_capacity_ledger_tenant_id"))
    op.execute(sa.schema.DropTable(ciaas_capacity_ledger, if_exists=True))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_ciaas_tenants_contract_id"))
    op.execute(sa.schema.DropTable(ciaas_tenants, if_exists=True))
