"""Studio API 스키마 — project/draft/render 제품 계층."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.domain.enums import (
    GenerationStatus,
    StudioCategory,
    StudioProjectStatus,
    StudioTemplateType,
    StudioTone,
)
from app.schemas.generation import IDEMPOTENCY_KEY_MAX_LENGTH, IDEMPOTENCY_KEY_PATTERN

StudioAssetId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$",
    ),
]


class StudioProjectCreateRequest(BaseModel):
    template_type: StudioTemplateType = StudioTemplateType.HAIR_STYLING_MOTION
    category: StudioCategory = StudioCategory.HAIR
    title: str = Field(min_length=1, max_length=120)
    offer_text: str = Field(min_length=1, max_length=500)
    cta_text: str = Field(min_length=1, max_length=120)
    duration_seconds: Literal[5, 15, 30] = 5
    target_audience: str | None = Field(default=None, max_length=120)
    tone: StudioTone = StudioTone.FRIENDLY
    asset_ids: list[StudioAssetId] = Field(default_factory=list, max_length=6)
    logo_asset_id: StudioAssetId | None = None
    disclaimer: str | None = Field(default=None, max_length=300)


class StudioScriptSchema(BaseModel):
    hook: str = Field(min_length=1, max_length=240)
    narration: list[str] = Field(min_length=1, max_length=6)
    cta: str = Field(min_length=1, max_length=120)


class StudioSceneSchema(BaseModel):
    scene_index: int = Field(ge=1, le=12)
    duration_seconds: int = Field(ge=1, le=10)
    caption: str = Field(min_length=1, max_length=160)
    visual_prompt: str = Field(min_length=1, max_length=400)


class StudioDraftSchema(BaseModel):
    version: int
    script: StudioScriptSchema
    storyboard: list[StudioSceneSchema] = Field(min_length=1, max_length=12)
    updated_at: datetime


class StudioDraftPatchRequest(BaseModel):
    script: StudioScriptSchema
    storyboard: list[StudioSceneSchema] = Field(min_length=1, max_length=12)


class StudioRenderRequest(BaseModel):
    idempotency_key: str = Field(
        min_length=1,
        max_length=IDEMPOTENCY_KEY_MAX_LENGTH,
        pattern=IDEMPOTENCY_KEY_PATTERN,
    )


class StudioStorageConfigResponse(BaseModel):
    backend: str
    storage_profile_name: str
    output_prefix: str
    output_retention_days: int


class StudioProjectResponse(BaseModel):
    project_id: str
    template_type: StudioTemplateType
    category: StudioCategory
    status: StudioProjectStatus
    title: str
    offer_text: str
    cta_text: str
    duration_seconds: int
    target_audience: str | None = None
    tone: StudioTone
    asset_ids: list[str]
    logo_asset_id: str | None = None
    disclaimer: str | None = None
    draft: StudioDraftSchema | None = None
    render_generation_id: str | None = None
    render_status: GenerationStatus | None = None
    output_asset_id: str | None = None
    storage: StudioStorageConfigResponse
    created_at: datetime
    updated_at: datetime


class StudioRenderResponse(BaseModel):
    project_id: str
    generation_id: str
    status: GenerationStatus
