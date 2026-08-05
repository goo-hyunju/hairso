"""에셋 라우터 — 얼굴 업로드 + 결과 다운로드. Router 는 HTTP 만(검증·저장은 Service).

업로드는 서버측 재검증(§4.14). 비공개 저장이므로 바이트는 이 API 를 통해서만 내려준다(§4.13).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.deps import get_asset_service, get_optional_user
from app.domain.errors import DomainError
from app.schemas.asset import AssetUploadResponse
from app.services.asset_service import AssetService

router = APIRouter(prefix="/api/v1", tags=["assets"])


@router.post("/assets", status_code=201, response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_service: AssetService = Depends(get_asset_service),
    user_id: str | None = Depends(get_optional_user),
) -> AssetUploadResponse:
    """얼굴 원본 업로드 → FACE_SOURCE 에셋. 실제 시그니처 재검증(§4.14)."""
    data = await file.read()
    try:
        asset = asset_service.upload_face(data, owner_id=user_id)
    except DomainError as exc:
        # 원문 대신 내부 오류코드만 노출(§3.12).
        raise HTTPException(status_code=400, detail=exc.error_code.value)
    return AssetUploadResponse(
        asset_id=asset.id,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
    )


@router.get("/assets/{asset_id}/content")
async def get_asset_content(
    asset_id: str,
    asset_service: AssetService = Depends(get_asset_service),
) -> Response:
    """에셋 바이트 다운로드(비공개 저장 → 이 API 경유). 없으면 404."""
    result = asset_service.get_bytes(asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    data, mime = result
    return Response(content=data, media_type=mime)
