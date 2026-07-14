"""생성 작업 라우터 — 비동기 202 + 상태 조회(규칙 §4.9).

Router 는 HTTP 만: 요청 검증 -> Service 위임 -> 응답 변환. SQL·외부호출 없음.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import (
    get_default_video_provider,
    get_generation_service,
    get_optional_user,
)
from app.domain.enums import GenerationStatus, GenerationType
from app.providers.video_generation.base import VideoGenerationInput
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.schemas.generation import (
    GenerationStatusResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from app.services.generation_service import GenerationService
from app.workers.generation_worker import GenerationWorker

router = APIRouter(prefix="/api/v1", tags=["generations"])

_TERMINAL = {GenerationStatus.SUCCEEDED, GenerationStatus.FAILED,
             GenerationStatus.CANCELED, GenerationStatus.EXPIRED}


async def _advance_mock_generation(generation_id: str, service: GenerationService) -> None:
    """[스캐폴드 데모] Mock 작업을 시간에 따라 전진시켜 상태 폴링을 실제처럼 보이게 한다.

    실서비스는 이 역할을 별도 Queue + Worker 프로세스가 맡는다(§4.9). 여기서는 단일 프로세스
    데모용으로만 BackgroundTask 를 쓴다 — 무거운 실작업이 아니라 in-memory Mock 전진일 뿐이다.
    """
    # 데모 진행 간격(초). 개발 서버 기본 1초(진행이 보이게), 테스트는 0으로 설정해 빠르게.
    interval = float(os.environ.get("MOCK_ADVANCE_INTERVAL_SEC", "1.0"))
    worker = GenerationWorker(service)
    provider = MockVideoProvider(MockScenario.SUCCESS, processing_polls=2)
    for _ in range(8):
        await asyncio.sleep(interval)
        gen = service.get_generation(generation_id)
        if gen is None or gen.status in _TERMINAL:
            break
        await worker.advance_once(gen, provider)


@router.post("/video-generations", status_code=202, response_model=VideoGenerationResponse)
async def create_video_generation(
    request: VideoGenerationRequest,
    background: BackgroundTasks,
    service: GenerationService = Depends(get_generation_service),
    user_id: str | None = Depends(get_optional_user),
) -> VideoGenerationResponse:
    """영상 생성 작업을 등록하고 202 + generation_id 를 반환한다(완료를 기다리지 않음).

    선택적 인증: 유효 토큰이 있으면 user_id 를 created_by 로 연결, 없으면 익명(None).
    """
    provider = get_default_video_provider()
    input_data = VideoGenerationInput(
        image_asset_id=request.image_asset_id,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        duration_seconds=request.duration_seconds,
        aspect_ratio=request.aspect_ratio,
        quality=request.quality,
        seed=request.seed,
        idempotency_key=request.idempotency_key,
    )
    gen = await service.create_video_generation(
        generation_id=str(uuid.uuid4()),
        consultation_id=request.consultation_id,
        input_data=input_data,
        provider=provider,
        created_by=user_id,
    )
    # [스캐폴드 데모] 새로 만든 작업만 Mock 전진(중복 idempotent 반환은 이미 진행 중).
    if gen.status is GenerationStatus.SUBMITTED and gen.generation_type is GenerationType.VIDEO:
        background.add_task(_advance_mock_generation, gen.id, service)
    return VideoGenerationResponse(generation_id=gen.id, status=gen.status)


@router.get("/generations/{generation_id}", response_model=GenerationStatusResponse)
async def get_generation(
    generation_id: str,
    service: GenerationService = Depends(get_generation_service),
) -> GenerationStatusResponse:
    """생성 작업 상태 조회(image/video 공통 정본, D3/P10)."""
    gen = service.get_generation(generation_id)
    if gen is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return GenerationStatusResponse(
        generation_id=gen.id,
        generation_type=gen.generation_type,
        status=gen.status,
        provider=gen.provider.value,
        # Decimal -> float(number) 변환 (와이어 계약, FE z.number()).
        estimated_cost_usd=(
            float(gen.estimated_cost_usd) if gen.estimated_cost_usd is not None else None
        ),
        output_asset_id=gen.output_asset_id,
        error_code=gen.error_code,
    )
