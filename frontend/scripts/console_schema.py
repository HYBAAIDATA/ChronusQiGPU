"""Audit-only Pydantic wire envelope. Not a new control-service dependency.

Nested owner documents deliberately remain extensible JSON: validating this
schema does not qualify their algorithms, hardware or per-field receipts.
"""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

class ReadyVerdict(BaseModel):
    model_config = ConfigDict(extra="allow")
    ready: StrictBool
    reason: StrictStr | None = None

class ConsoleSources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fabric: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    selftest: dict[str, Any] | None = None
    agentic: dict[str, Any] | None = None
    campaign: dict[str, Any] | None = None
    telemetry: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    intelligence: dict[str, Any] | None = None
    cognition: dict[str, Any] | None = None
    unavailable: dict[str, StrictStr] = {}

class ConsoleStatus(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["chronus.mla1517.status/1"]
    generated_at: StrictStr
    ready_to_mine: ReadyVerdict | None = None
    console: ConsoleSources | None = None
