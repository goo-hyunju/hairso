"""에셋 스키마 — 업로드 응답(snake_case). 원본/공개 URL 은 응답에 담지 않는다(§4.13)."""

from __future__ import annotations

from pydantic import BaseModel


class AssetUploadResponse(BaseModel):
    asset_id: str
    asset_type: str
    mime_type: str
    byte_size: int
