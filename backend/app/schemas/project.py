"""Pydantic v2 schemas for project endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    polygon_geojson: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    latitude: float
    longitude: float
    address: str | None
    polygon_geojson: dict[str, Any] | None
    created_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None
    total: int
