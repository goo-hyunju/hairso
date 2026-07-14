"""상담 라우터 — [일부구현·스캐폴드]. 실 DB 미연결(인메모리 로드맵)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.consultation import (
    ConsultationCreateRequest,
    ConsultationResponse,
)

router = APIRouter(prefix="/api/v1", tags=["consultations"])


@router.post("/consultations", status_code=201, response_model=ConsultationResponse)
async def create_consultation(
    request: ConsultationCreateRequest,
) -> ConsultationResponse:
    # 스캐폴드: 실제 저장은 로드맵(Repository·DB). 계약 형태만 반환.
    return ConsultationResponse(
        consultation_id=str(uuid.uuid4()),
        status="OPEN",
        memo=None,
        created_at=datetime.now(timezone.utc),
    )
