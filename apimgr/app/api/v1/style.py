"""스타일 분석 라우터 — 단발 동기 호출(§4.11 트랜잭션 밖). Mock 분석 Provider 사용."""

from __future__ import annotations

from fastapi import APIRouter

from app.providers.image_analysis.base import StyleAnalysisInput
from app.providers.image_analysis.mock import MockImageAnalysisProvider
from app.schemas.style import HairStructureSchema, StyleAnalyzeRequest, StyleAnalyzeResponse

router = APIRouter(prefix="/api/v1", tags=["style"])


@router.post("/style/analyze", response_model=StyleAnalyzeResponse)
async def analyze_style(request: StyleAnalyzeRequest) -> StyleAnalyzeResponse:
    """참고 사진에서 헤어 구조만 추출(연예인 이름 미저장, §6.1/§18)."""
    provider = MockImageAnalysisProvider()  # 기본 Mock(§0.16)
    result = await provider.analyze_style(
        StyleAnalysisInput(
            reference_asset_id=request.reference_asset_id,
            text_hint=request.text_hint,
        )
    )
    return StyleAnalyzeResponse(
        structure=HairStructureSchema(**result.structure.to_dict()),
        warnings=result.warnings,
    )
