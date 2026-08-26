"""Studio draft provider 공통 계약.

Draft provider 는 script/storyboard JSON 초안을 만드는 텍스트 생성 계층이다. 고객 이미지 바이트,
signed URL, provider raw payload 를 받거나 반환하지 않는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.enums import StudioCategory, StudioTemplateType, StudioTone
from app.domain.studio import StudioDraft


class StudioDraftProviderError(Exception):
    """초안 provider 실패. Service 는 이 오류를 안전한 Mock fallback 으로 바꿀 수 있다."""


@dataclass(frozen=True)
class StudioDraftInput:
    template_type: StudioTemplateType
    category: StudioCategory
    title: str
    offer_text: str
    cta_text: str
    duration_seconds: int
    target_audience: str | None
    tone: StudioTone
    asset_count: int
    has_logo: bool
    disclaimer: str | None


class StudioDraftProvider(ABC):
    @abstractmethod
    def create_draft(self, data: StudioDraftInput) -> StudioDraft:
        """Studio draft schema 에 맞는 script/storyboard 초안을 생성한다."""
