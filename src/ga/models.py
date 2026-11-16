"""Validated request models preserved from the v3 research API surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class StoreRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: dict[str, Any]
    sector: str = Field(default="general", min_length=1, max_length=64)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if any(not (character.isalnum() or character in "_-") for character in value):
            raise ValueError("key must be alphanumeric with underscores or hyphens")
        return value


class QueryRequest(BaseModel):
    center_key: str = Field(..., min_length=1, max_length=255)
    radius: float = Field(default=1.0, ge=0, le=1_000_000)
    sector: str | None = Field(default=None, max_length=64)


class SearchRequest(BaseModel):
    target_hash: str = Field(..., min_length=1, max_length=128)
    algorithm: str = Field(default="golden", pattern="^(golden|galois|ricci)$")


class NonceRequest(BaseModel):
    block_header: str = Field(..., min_length=1, max_length=4096)
    difficulty_target: int = Field(..., gt=0)
