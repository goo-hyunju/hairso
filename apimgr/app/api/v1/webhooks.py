"""Provider Webhook 라우터 — 서명검증·중복안전(규칙 §4.15).

무거운 다운로드·FFmpeg 는 여기서 하지 않는다. 검증·상태반영만 빠르게.
스캐폴드: 서명 검증 로직은 WebhookService 에 있고, 여기선 원문 payload·헤더를 전달한다.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.deps import get_webhook_service
from app.core.config import get_settings
from app.domain.enums import ProviderJobStatus
from app.domain.errors import WebhookSignatureInvalid
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


@router.post("/webhooks/pixverse", status_code=200)
async def pixverse_webhook(
    request: Request,
    x_signature: str = Header(default=""),
    x_timestamp: int = Header(default=0),
    x_event_id: str = Header(default=""),
    service: WebhookService = Depends(get_webhook_service),
) -> dict[str, str]:
    """[스텁] PixVerse webhook. 서명 검증 후 상태 반영. 실 payload 스키마는 로드맵."""
    payload = await request.body()
    settings = get_settings()
    if not settings.pixverse_webhook_secret:
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")
    # 실제 파싱은 로드맵 — 스캐폴드는 헤더 기반 최소 흐름만.
    external_job_id = request.query_params.get("job_id", "")
    now_ts = int(time.time())
    try:
        status = service.handle_status_event(
            secret=settings.pixverse_webhook_secret,
            payload=payload,
            signature=x_signature,
            event_ts=x_timestamp,
            now_ts=now_ts,
            event_id=x_event_id,
            provider="PIXVERSE",
            external_job_id=external_job_id,
            provider_status=ProviderJobStatus.PROCESSING,
        )
    except WebhookSignatureInvalid as exc:
        raise HTTPException(status_code=400, detail="WEBHOOK_SIGNATURE_INVALID") from exc
    return {"received": "ok", "status": status}
