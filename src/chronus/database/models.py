"""ORM Models for Thesus Database System.

SQLAlchemy ORM models for workload records, node registry, configurations,
verification receipts, and audit logs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base

def _record_constructor(self, **kwargs) -> None:
    """Declarative constructor accepting the public ``metadata`` keyword.

    ``metadata`` is reserved by the SQLAlchemy Declarative API, so the mapped
    attribute is ``metadata_`` (column name stays ``metadata``). The public
    ``metadata=`` keyword is translated for API compatibility.
    """
    if "metadata" in kwargs:
        kwargs["metadata_"] = kwargs.pop("metadata")
    for key, value in kwargs.items():
        if not hasattr(type(self), key):
            raise TypeError(f"{type(self).__name__!r} has no attribute {key!r}")
        setattr(self, key, value)


Base = declarative_base(constructor=_record_constructor)


class WorkloadRecord(Base):
    """ORM model for Chronus computational workload records."""

    __tablename__ = "workloads"

    id = Column(UUID, primary_key=True, server_default="gen_random_uuid()")
    payload_hash = Column(String(64), nullable=False, index=True)
    payload_bytes = Column(Text, nullable=False)
    workload_type = Column(String(128), nullable=False)
    representation_mode = Column(String(64), nullable=False)
    priority = Column(String(20), nullable=False)
    tenant_id = Column(String(128), nullable=False, index=True)
    region = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False)
    ccu_cost = Column(Float, nullable=True)
    result = Column(JSONB, nullable=True)
    verification_receipt = Column(String(64), nullable=True)
    submitted_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "payload_hash": self.payload_hash,
            "payload_bytes": self.payload_bytes,
            "workload_type": self.workload_type,
            "representation_mode": self.representation_mode,
            "priority": self.priority,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "status": self.status,
            "ccu_cost": self.ccu_cost,
            "result": self.result,
            "verification_receipt": self.verification_receipt,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata_,
        }


class NodeRecord(Base):
    """ORM model for cluster node registry."""

    __tablename__ = "nodes"

    id = Column(UUID, primary_key=True, server_default="gen_random_uuid()")
    hostname = Column(String(256), nullable=False, unique=True)
    region = Column(String(64), nullable=False)
    capacity = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    last_heartbeat = Column(DateTime, nullable=True)
    workloads_assigned = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "hostname": self.hostname,
            "region": self.region,
            "capacity": self.capacity,
            "status": self.status,
            "last_heartbeat": (
                self.last_heartbeat.isoformat() if self.last_heartbeat else None
            ),
            "workloads_assigned": self.workloads_assigned,
            "metadata": self.metadata_,
        }


class ConfigRecord(Base):
    """ORM model for Chronus configuration records."""

    __tablename__ = "configurations"

    id = Column(UUID, primary_key=True, server_default="gen_random_uuid()")
    key = Column(String(256), nullable=False, unique=True, index=True)
    value = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReceiptRecord(Base):
    """ORM model for verification receipts."""

    __tablename__ = "receipts"

    id = Column(UUID, primary_key=True, server_default="gen_random_uuid()")
    hash_value = Column(String(64), nullable=False, unique=True, index=True)
    ml_dsa_signature = Column(Text, nullable=True)
    ed25519_signature = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    latency_ms = Column(Float, nullable=False, default=0.0)
    validity = Column(Boolean, nullable=False, default=False)
    metadata_ = Column("metadata", JSONB, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "hash_value": self.hash_value,
            "ml_dsa_signature": self.ml_dsa_signature,
            "ed25519_signature": self.ed25519_signature,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "latency_ms": self.latency_ms,
            "validity": self.validity,
            "metadata": self.metadata_,
        }