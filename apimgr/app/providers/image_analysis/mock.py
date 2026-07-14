"""Mock 이미지 분석 Provider — 고정 헤어 구조를 결정적으로 반환(외부 호출 없음)."""

from __future__ import annotations

from app.providers.image_analysis.base import (
    HairStructure,
    ImageAnalysisProvider,
    StyleAnalysisInput,
    StyleAnalysisResult,
)


class MockImageAnalysisProvider(ImageAnalysisProvider):
    async def analyze_style(self, data: StyleAnalysisInput) -> StyleAnalysisResult:
        # 결정적 더미 구조(§5 단계4 예시 기반). 실제 Gemini 분석 아님.
        structure = HairStructure(
            length="jaw_length_bob",
            bangs="thin_see_through",
            parting="slightly_off_center",
            curl="soft_inward_c_curl",
            crown_volume="low",
            side_volume="medium",
            color="dark_chocolate_brown",
            layer_position="below_cheekbone",
            overall_mood="natural_elegant",
        )
        return StyleAnalysisResult(structure=structure, warnings=[])
