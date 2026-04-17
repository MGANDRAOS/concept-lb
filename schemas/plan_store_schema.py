# schemas/plan_store_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, Field

PlanStatus = Literal["draft", "complete", "failed"]

class PlanRecordCreate(BaseModel):
    """
    What we write into DB.
    JSON fields are dicts here (we store as TEXT in sqlite).
    """
    id: str
    created_at: str
    updated_at: str
    status: PlanStatus

    title: Optional[str] = None
    mode: Optional[str] = None
    locale: Optional[str] = None
    model: Optional[str] = None
    job_id: Optional[str] = None

    intake: Dict[str, Any] = Field(default_factory=dict)
    normalized_intake: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    plan_html: Optional[str] = None

    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None

class PlanListItem(BaseModel):
    id: str
    created_at: str
    status: PlanStatus
    title: Optional[str] = None
    locale: Optional[str] = None
    mode: Optional[str] = None
    model: Optional[str] = None

class PlanView(BaseModel):
    id: str
    created_at: str
    updated_at: str
    status: PlanStatus

    title: Optional[str] = None
    mode: Optional[str] = None
    locale: Optional[str] = None
    model: Optional[str] = None
    job_id: Optional[str] = None

    intake: Dict[str, Any]
    normalized_intake: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    plan_html: Optional[str] = None

    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    stale_section_ids: list[str] = Field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"