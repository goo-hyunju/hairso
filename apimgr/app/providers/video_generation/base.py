"""영상 생성 Provider 공통 인터페이스 (규칙 §4.6/§12).

입력은 image_asset_id(UUID) — 기획서 §12 의 imageUrl 이 아니다(규칙 §4.6/§0.15: 얼굴 URL 미노출).
비용은 Decimal(§11-2). status 는 ProviderJobStatus(4값) — 내부 GenerationStatus 와 다른 레이어.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName


@dataclass(frozen=True)
class VideoGenerationInput:
    image_asset_id: str  # UUID 문자열(Pydantic 요청 스키마 계층에서 형식 검증)
    prompt: str
    duration_seconds: int  # MVP 5, 확장 8 (Pydantic 요청 스키마에서 Literal[5,8] 검증)
    aspect_ratio: str  # "9:16" | "16:9" | "1:1"
    quality: str  # "480p" | "720p" | "1080p"
    idempotency_key: str
    negative_prompt: str | None = None
    seed: int | None = None


@dataclass(frozen=True)
class VideoSubmissionResult:
    provider: ProviderName
    external_job_id: str
    ai_trace_id: str | None = None  # PixVerse 전용 — provider 내부에서 채움
    estimated_cost_usd: Decimal | None = None


@dataclass(frozen=True)
class VideoStatusResult:
    status: ProviderJobStatus
    output_url: str | None = None
    error_code: ErrorCode | None = None


class VideoProvider(ABC):
    """모든 영상 Provider 구현이 따르는 계약."""

    @abstractmethod
    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        """생성 작업을 제출하고 외부 작업 ID 를 받는다."""

    @abstractmethod
    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        """외부 작업 상태를 폴링한다."""
