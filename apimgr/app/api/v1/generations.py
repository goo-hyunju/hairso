"""생성 작업 라우터 — 비동기 202 + 상태 조회(규칙 §4.9).

Router 는 HTTP 만: 요청 검증 -> Service 위임 -> 응답 변환. SQL·외부호출 없음.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import (
    get_asset_service,
    get_default_image_provider,
    get_default_video_provider,
    get_generation_service,
    get_optional_user,
)
from app.domain.enums import ErrorCode, GenerationStatus, GenerationType, ProviderJobStatus
from app.domain.errors import DomainError
from app.providers.image_generation.base import (
    ImageGenerationInput,
    ImageProvider,
    ImageVariant,
)
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoSourceImage,
)
from app.providers.video_generation.mock import MockVideoProvider
from app.schemas.generation import (
    GenerationStatusResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService
from app.workers.generation_worker import GenerationWorker, video_polling_config

router = APIRouter(prefix="/api/v1", tags=["generations"])

GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
OptionalUserDep = Annotated[str | None, Depends(get_optional_user)]

_TERMINAL = {GenerationStatus.SUCCEEDED, GenerationStatus.FAILED,
             GenerationStatus.CANCELED, GenerationStatus.EXPIRED}

# 조회발 전진·백그라운드 폴러의 동시 중복 전진 방지(결과 다운로드·asset 등록이 겹치지 않게).
_advance_inflight: set[str] = set()


def _raise_generation_http(exc: DomainError) -> None:
    status = 409 if exc.error_code is ErrorCode.GENERATION_DUPLICATED else 400
    raise HTTPException(status_code=status, detail=exc.error_code.value) from exc


def is_video_advance_inflight(generation_id: str) -> bool:
    return generation_id in _advance_inflight


async def advance_stalled_video_generation(
    gen,
    service: GenerationService,
    asset_service: AssetService,
):
    """[스캐폴드 데모] 상태 조회 시점에 비터미널 VIDEO 작업을 provider 로 1회 전진시킨다.

    BackgroundTask 폴러는 BE 재시작(reload)과 함께 사라져 작업이 PROCESSING 에 영구히 남는다.
    self-hosted 상태 원본은 ml 서버 job 이므로(외부 job_id 로 재조회 가능) FE 상태 폴링이
    이 경로로 전진을 이어받으면 재시작 후에도 완료/실패가 반영된다.
    """
    if gen.generation_type is not GenerationType.VIDEO or gen.status in _TERMINAL:
        return gen
    if not gen.external_job_id or gen.id in _advance_inflight:
        return gen
    provider = get_default_video_provider()
    if isinstance(provider, MockVideoProvider):
        # Mock 은 provider 인스턴스 내부 상태라 새 인스턴스로 조회 불가 — 데모 폴러가 담당.
        return gen
    _advance_inflight.add(gen.id)
    try:
        worker = GenerationWorker(service, asset_service)
        await worker.advance_once(gen, provider)
    except Exception:  # noqa: BLE001
        # 조회 응답은 현재 상태로 성공시키고 전진은 다음 폴링이 재시도한다(전진 실패 ≠ 조회 실패).
        return gen
    finally:
        _advance_inflight.discard(gen.id)
    return service.get_generation(gen.id) or gen


async def _advance_video_generation(
    generation_id: str,
    service: GenerationService,
    asset_service: AssetService,
    provider: VideoProvider,
) -> None:
    """[스캐폴드 데모] 제출에 사용한 영상 provider 를 폴링해 상태를 전진시킨다.

    실서비스는 이 역할을 별도 Queue + Worker 프로세스가 맡는다(§4.9). 여기서는 단일 프로세스
    데모용 BackgroundTask 로만 실행한다. 긴 self-hosted render 는 전용 worker 로 분리해야 한다.
    """
    interval, max_polls = video_polling_config()
    worker = GenerationWorker(service, asset_service)
    for _ in range(max_polls):
        await asyncio.sleep(interval)
        gen = service.get_generation(generation_id)
        if gen is None or gen.status in _TERMINAL:
            break
        if gen.id in _advance_inflight:
            continue  # 조회발 전진이 진행 중 — 이번 tick 은 건너뛴다
        try:
            await worker.advance_once(gen, provider)
        except Exception:  # noqa: BLE001
            service.fail_generation(gen, GenerationType.VIDEO, ErrorCode.GENERATION_FAILED)
            break
    else:
        gen = service.get_generation(generation_id)
        if gen is not None and gen.status not in _TERMINAL:
            service.fail_generation(gen, GenerationType.VIDEO, ErrorCode.GENERATION_FAILED)


@router.post("/video-generations", status_code=202, response_model=VideoGenerationResponse)
async def create_video_generation(
    request: VideoGenerationRequest,
    background: BackgroundTasks,
    service: GenerationServiceDep,
    asset_service: AssetServiceDep,
    user_id: OptionalUserDep,
) -> VideoGenerationResponse:
    """영상 생성 작업을 등록하고 202 + generation_id 를 반환한다(완료를 기다리지 않음).

    선택적 인증: 유효 토큰이 있으면 user_id 를 created_by 로 연결, 없으면 익명(None).
    """
    provider = get_default_video_provider()
    generation_id = str(uuid.uuid4())
    source_image: VideoSourceImage | None = None
    if not isinstance(provider, MockVideoProvider):
        try:
            data, content_type = asset_service.load_reference_bytes(
                request.image_asset_id,
                user_id,
                {"FACE_SOURCE", "GENERATED_IMAGE"},
            )
        except DomainError as exc:
            raise HTTPException(status_code=400, detail=exc.error_code.value) from exc
        source_image = VideoSourceImage(data=data, content_type=content_type)
    input_data = VideoGenerationInput(
        image_asset_id=request.image_asset_id,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        duration_seconds=request.duration_seconds,
        aspect_ratio=request.aspect_ratio,
        quality=request.quality,
        seed=request.seed,
        idempotency_key=request.idempotency_key,
        source_image=source_image,
    )
    try:
        gen = await service.create_video_generation(
            generation_id=generation_id,
            consultation_id=request.consultation_id,
            input_data=input_data,
            provider=provider,
            created_by=user_id,
        )
    except DomainError as exc:
        _raise_generation_http(exc)
    # [스캐폴드 데모] 새로 만든 작업만 Mock 전진(중복 idempotent 반환은 이미 진행 중).
    if (
        gen.id == generation_id
        and gen.status is GenerationStatus.SUBMITTED
        and gen.generation_type is GenerationType.VIDEO
    ):
        background.add_task(_advance_video_generation, gen.id, service, asset_service, provider)
    return VideoGenerationResponse(generation_id=gen.id, status=gen.status)


async def _run_image_generation(
    generation_id: str,
    input_data: ImageGenerationInput,
    consultation_id: str,
    gen_service: GenerationService,
    asset_service: AssetService,
    provider: ImageProvider,
) -> None:
    """이미지 생성 실작업(백그라운드) — provider 제출 → 결과 에셋 등록 → SUCCEEDED.

    로컬 provider 는 submit 에서 추론+결과저장을 마치므로 get_status 가 즉시 SUCCEEDED 를 보고한다.
    IMAGE 는 후처리(POST_PROCESSING) 없이 provider SUCCEEDED -> 내부 SUCCEEDED(§4.16).
    """
    gen = gen_service.get_generation(generation_id)
    if gen is None:
        return
    try:
        result = await provider.submit(input_data)
        gen = gen_service.mark_submitted(
            gen, result.provider, result.external_job_id, result.estimated_cost_usd
        )

        status = await provider.get_status(result.external_job_id)
        if status.status is ProviderJobStatus.SUCCEEDED and status.output_url:
            asset = asset_service.register_generated_image(status.output_url, consultation_id)
            gen_service.complete_generation(gen, GenerationType.IMAGE, output_asset_id=asset.id)
        elif status.status is ProviderJobStatus.FAILED:
            gen_service.fail_generation(
                gen, GenerationType.IMAGE, status.error_code or ErrorCode.GENERATION_FAILED
            )
    except DomainError as exc:
        gen_service.fail_generation(gen, GenerationType.IMAGE, exc.error_code, str(exc))
    except Exception:  # noqa: BLE001
        # 원문 예외·경로·payload 는 사용자 응답/로그에 노출하지 않는다. 실서비스 로깅은 ID 중심.
        gen_service.fail_generation(gen, GenerationType.IMAGE, ErrorCode.GENERATION_FAILED)

@router.post("/image-generations", status_code=202, response_model=ImageGenerationResponse)
async def create_image_generation(
    request: ImageGenerationRequest,
    background: BackgroundTasks,
    service: GenerationServiceDep,
    asset_service: AssetServiceDep,
    user_id: OptionalUserDep,
) -> ImageGenerationResponse:
    """이미지 헤어 리스타일 작업 등록(§6.1). 202 + generation_id, 실작업은 백그라운드."""
    provider = get_default_image_provider()
    generation_id = str(uuid.uuid4())
    input_data = ImageGenerationInput(
        face_asset_id=request.face_asset_id,
        style_reference_asset_id=request.style_reference_asset_id,
        style_structure={},  # 스타일 분석 결과 연결은 로드맵
        variant=ImageVariant(request.variant),
        prompt=request.prompt,
        idempotency_key=request.idempotency_key,
        negative_prompt=request.negative_prompt,
    )
    try:
        gen = service.create_image_generation_record(
            generation_id=generation_id,
            consultation_id=request.consultation_id,
            input_data=input_data,
            created_by=user_id,
        )
    except DomainError as exc:
        _raise_generation_http(exc)
    # 새로 만든 작업만 실행(중복 idempotent 반환은 이미 진행/완료).
    if gen.id == generation_id and gen.status is GenerationStatus.CREATED:
        background.add_task(
            _run_image_generation,
            gen.id,
            input_data,
            request.consultation_id,
            service,
            asset_service,
            provider,
        )
    return ImageGenerationResponse(generation_id=gen.id, status=gen.status)


@router.get("/generations/{generation_id}", response_model=GenerationStatusResponse)
async def get_generation(
    generation_id: str,
    service: GenerationServiceDep,
    asset_service: AssetServiceDep,
) -> GenerationStatusResponse:
    """생성 작업 상태 조회(image/video 공통 정본, D3/P10)."""
    gen = service.get_generation(generation_id)
    if gen is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    gen = await advance_stalled_video_generation(gen, service, asset_service)
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
