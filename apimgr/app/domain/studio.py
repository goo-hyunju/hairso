"""Studio 도메인 모델 — 제품 레이어(project/draft/render)를 생성 job 과 분리한다.

Studio 최종 영상 길이(5/15/30초)는 여기 보관하고, low-level provider clip 생성 계약(5/8초)은
기존 GenerationService 에 그대로 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import StudioCategory, StudioProjectStatus, StudioTemplateType, StudioTone
from app.domain.models import _utcnow


@dataclass
class StudioScript:
    hook: str
    narration: list[str]
    cta: str


@dataclass
class StudioScene:
    scene_index: int
    duration_seconds: int
    caption: str
    visual_prompt: str


@dataclass
class StudioDraft:
    script: StudioScript
    storyboard: list[StudioScene]
    version: int = 1
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class StudioProject:
    id: str
    template_type: StudioTemplateType
    category: StudioCategory
    title: str
    offer_text: str
    cta_text: str
    duration_seconds: int
    target_audience: str | None = None
    tone: StudioTone = StudioTone.FRIENDLY
    asset_ids: list[str] = field(default_factory=list)
    logo_asset_id: str | None = None
    disclaimer: str | None = None
    status: StudioProjectStatus = StudioProjectStatus.DRAFTING
    created_by: str | None = None
    storage_profile_name: str = "local-dev"
    draft: StudioDraft | None = None
    render_generation_id: str | None = None
    output_asset_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
