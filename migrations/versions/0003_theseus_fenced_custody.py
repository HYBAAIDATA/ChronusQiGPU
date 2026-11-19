"""Create the fenced custody edge schema with populated-table downgrade guards."""
from alembic import op
import sqlalchemy as sa

revision = "0003_theseus_fenced_custody"
down_revision = "0002_ciaas_tenancy_tables"
branch_labels = None
depends_on = None

_meta = sa.MetaData()
_int = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
receipts = sa.Table(
    "theseus_fenced_receipts", _meta,
    sa.Column("seq", _int, primary_key=True, autoincrement=False),
    sa.Column("node_id", sa.Text(), nullable=False),
    sa.Column("slot_id", sa.Text(), nullable=False),
    sa.Column("tenant_id", sa.Text(), nullable=False),
    sa.Column("fencing_epoch", _int, nullable=False),
    sa.Column("ts_ns", _int, nullable=False),
    sa.Column("event_type", sa.Text(), nullable=False),
    sa.Column("payload_json", sa.LargeBinary(), nullable=False),
    sa.Column("payload_digest", sa.LargeBinary(), nullable=False),
    sa.Column("prev_hash", sa.LargeBinary(), nullable=False),
    sa.Column("record_hash", sa.LargeBinary(), nullable=False),
)
anchors = sa.Table(
    "theseus_epoch_anchors", _meta,
    sa.Column("seq_end", _int, primary_key=True, autoincrement=False),
    sa.Column("seq_start", _int, nullable=False),
    sa.Column("fencing_epoch", _int, nullable=False),
    sa.Column("anchor_kind", sa.Text(), nullable=False),
    sa.Column("leaf_count", _int, nullable=False),
    sa.Column("merkle_root", sa.LargeBinary(), nullable=False),
    sa.Column("head_record_hash", sa.LargeBinary(), nullable=False),
    sa.Column("anchored_ts_ns", _int, nullable=False),
    sa.Column("signer_key_id", sa.Text(), nullable=False),
    sa.Column("hardware_backed", sa.Integer(), nullable=False),
    sa.Column("signature", sa.LargeBinary(), nullable=False),
    sa.Column("quorum_revision", _int, nullable=False),
)
fences = sa.Table(
    "theseus_local_fences", _meta,
    sa.Column("slot_key", sa.Text(), primary_key=True),
    sa.Column("epoch", _int, nullable=False),
)
index = sa.Index("idx_theseus_tenant_seq", receipts.c.tenant_id, receipts.c.seq)
_tables = (receipts, anchors, fences)

def upgrade() -> None:
    for table in _tables:
        op.execute(sa.schema.CreateTable(table, if_not_exists=True))
    op.execute(sa.schema.CreateIndex(index, if_not_exists=True))

def downgrade() -> None:
    context = op.get_context()
    tables = tuple(reversed(_tables))
    if context.as_sql:
        if context.dialect.name != "postgresql":
            raise RuntimeError("Offline custody downgrade requires PostgreSQL lock guards")
        for table in tables:
            name = table.name
            op.execute(sa.text(
                "DO $$ DECLARE has_rows boolean; BEGIN "
                f"IF to_regclass('{name}') IS NOT NULL THEN "
                f"EXECUTE 'LOCK TABLE {name} IN ACCESS EXCLUSIVE MODE'; "
                f"EXECUTE 'SELECT EXISTS (SELECT 1 FROM {name})' INTO has_rows; "
                f"IF has_rows THEN RAISE EXCEPTION 'refusing to downgrade 0003: {name} contains rows'; "
                "END IF; END IF; END $$"
            ))
    else:
        bind = op.get_bind()
        existing = set(sa.inspect(bind).get_table_names())
        if context.dialect.name == "postgresql":
            for table in tables:
                if table.name in existing:
                    op.execute(sa.text(f'LOCK TABLE "{table.name}" IN ACCESS EXCLUSIVE MODE'))
        elif context.dialect.name == "sqlite":
            # Acquire the SQLite write lock before any emptiness checks.
            bind.exec_driver_sql("UPDATE theseus_local_fences SET epoch = epoch WHERE 0") if fences.name in existing else None
        else:
            raise RuntimeError("Unsupported custody downgrade dialect")
        for table in tables:
            if table.name in existing and bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one():
                raise RuntimeError(f"refusing to downgrade 0003: {table.name} contains rows")
    op.execute(sa.schema.DropIndex(index, if_exists=True))
    for table in tables:
        op.execute(sa.schema.DropTable(table, if_exists=True))
