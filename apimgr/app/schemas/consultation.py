"""상담 스키마(§15 /consultations)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConsultationCreateRequest(BaseModel):
    salon_id: str | None = None
    customer_id: str | None = None


class ConsultationResponse(BaseModel):
    consultation_id: str
    status: str
    memo: str | None = None
    created_at: datetime


class ConsultationPatchRequest(BaseModel):
    memo: str | None = None
    status: str | None = None
