"""스타일 분석·추천 스키마(§15 /style/analyze, /style/recommend)."""

from __future__ import annotations

from pydantic import BaseModel


class StyleAnalyzeRequest(BaseModel):
    consultation_id: str
    reference_asset_id: str
    text_hint: str | None = None


class HairStructureSchema(BaseModel):
    length: str
    bangs: str
    parting: str
    curl: str
    crown_volume: str
    side_volume: str
    color: str
    layer_position: str
    overall_mood: str


class StyleAnalyzeResponse(BaseModel):
    structure: HairStructureSchema
    warnings: list[str] = []
