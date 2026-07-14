"""이미지 생성 Provider 공통 인터페이스.

고객 얼굴은 유지하고 헤어스타일만 적용(규칙 §6.1). 3종 변형(§5 단계6):
    SIMILAR(참고 최유사) / FACE_ADJUSTED(얼굴형 보정) / EASY_CARE(관리 쉬운 현실형).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName


class ImageVariant(str, Enum):
    SIMILAR = "SIMILAR"
    FACE_ADJUSTED = "FACE_ADJUSTED"
    EASY_CARE = "EASY_CARE"


@dataclass(frozen=True)
class ImageGenerationInput:
    face_asset_id: str
    style_reference_asset_id: str | None
    style_structure: dict[str, str]  # {length,bangs,parting,curl,...}
    variant: ImageVariant
    prompt: str
    idempotency_key: str
    negative_prompt: str | None = None


@dataclass(frozen=True)
class ImageSubmissionResult:
    provider: ProviderName
    external_job_id: str
    estimated_cost_usd: Decimal | None = None


@dataclass(frozen=True)
class ImageStatusResult:
    status: ProviderJobStatus
    output_url: str | None = None
    error_code: ErrorCode | None = None


class ImageProvider(ABC):
    @abstractmethod
    async def submit(self, data: ImageGenerationInput) -> ImageSubmissionResult:
        ...

    @abstractmethod
    async def get_status(self, external_job_id: str) -> ImageStatusResult:
        ...
