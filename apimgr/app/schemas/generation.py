"""생성 작업 스키마 — 요청/응답(snake_case)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import ErrorCode, GenerationStatus, GenerationType

IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._-]+$"
IDEMPOTENCY_KEY_MAX_LENGTH = 128


class VideoGenerationRequest(BaseModel):
    # id 는 스캐폴드에서 opaque 문자열(UUID 형식 검증은 실 DB 계층 로드맵 — api-contract 참조).
    consultation_id: str = Field(min_length=1)
    image_asset_id: str = Field(min_length=1)  # 규칙 §4.6: URL 이 아닌 asset_id
    prompt: str = Field(min_length=1)  # 빈 프롬프트 거부
    negative_prompt: str | None = None
    duration_seconds: Literal[5, 8] = 5  # MVP 기본 5(§15)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    quality: Literal["480p", "720p", "1080p"] = "720p"
    seed: int | None = None
    idempotency_key: str = Field(
        min_length=1,
        max_length=IDEMPOTENCY_KEY_MAX_LENGTH,
        pattern=IDEMPOTENCY_KEY_PATTERN,
    )


class VideoGenerationResponse(BaseModel):
    """202 Accepted 응답 — 작업 등록 완료."""

    generation_id: str
    status: GenerationStatus


class ImageGenerationRequest(BaseModel):
    """이미지 헤어 리스타일 생성 요청(§6.1 얼굴 유지 + 머리만 변경)."""

    consultation_id: str = Field(min_length=1)
    face_asset_id: str = Field(min_length=1)  # 업로드로 확보한 FACE_SOURCE asset
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    variant: Literal["SIMILAR", "FACE_ADJUSTED", "EASY_CARE"] = "SIMILAR"
    style_reference_asset_id: str | None = None
    idempotency_key: str = Field(
        min_length=1,
        max_length=IDEMPOTENCY_KEY_MAX_LENGTH,
        pattern=IDEMPOTENCY_KEY_PATTERN,
    )


class ImageGenerationResponse(BaseModel):
    """202 Accepted — 이미지 생성 작업 등록 완료."""

    generation_id: str
    status: GenerationStatus


class GenerationStatusResponse(BaseModel):
    """GET /api/v1/generations/{id} — image/video 공통."""

    generation_id: str
    generation_type: GenerationType
    status: GenerationStatus
    provider: str | None = None
    # 와이어는 number(float) — FE Zod `z.number()` 와 계약 일치.
    # 도메인·DB 는 Decimal/numeric(정밀). Pydantic 은 Decimal 을 JSON string 으로 직렬화하므로
    # 여기서 float 타입으로 노출해 number 로 나가게 한다(라우터에서 변환).
    estimated_cost_usd: float | None = None
    output_asset_id: str | None = None
    error_code: ErrorCode | None = None
