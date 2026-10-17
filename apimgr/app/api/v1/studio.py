"""Studio API — project/draft/render 제품 계층.

Router 는 HTTP 요청/응답 변환만 담당하고, draft 생성과 render 연결은 StudioService 로 위임한다.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import (
    get_asset_service,
    get_default_video_provider,
    get_generation_service,
    get_optional_user,
    get_settings,
    get_studio_service,
)
from app.api.v1.generations import advance_stalled_video_generation, is_video_advance_inflight
from app.domain.enums import ErrorCode, GenerationStatus
from app.domain.errors import DomainError
from app.domain.studio import StudioDraft, StudioProject, StudioScene, StudioScript
from app.providers.video_generation.base import VideoProvider
from app.schemas.studio import (
    StudioDraftPatchRequest,
    StudioDraftSchema,
    StudioProjectCreateRequest,
    StudioProjectResponse,
    StudioRenderRequest,
    StudioRenderResponse,
    StudioSceneSchema,
    StudioScriptSchema,
    StudioStorageConfigResponse,
)
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService
from app.services.studio_service import StudioService
from app.workers.generation_worker import GenerationWorker, video_polling_config

router = APIRouter(prefix="/api/v1/studio", tags=["studio"])

StudioServiceDep = Annotated[StudioService, Depends(get_studio_service)]
GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
OptionalUserDep = Annotated[str | None, Depends(get_optional_user)]

_TERMINAL = {
    GenerationStatus.SUCCEEDED,
    GenerationStatus.FAILED,
    GenerationStatus.CANCELED,
    GenerationStatus.EXPIRED,
}

_DOWNLOAD_EXTENSIONS = {
    "video/mp4": "mp4",
}


async def _advance_video_generation(
    generation_id: str,
    service: GenerationService,
    asset_service: AssetService,
    provider: VideoProvider,
) -> None:
    """Studio render job 전진. 실서비스는 DB job + 별도 Worker 로 이동한다."""
    interval, max_polls = video_polling_config()
    worker = GenerationWorker(service, asset_service)
    for _ in range(max_polls):
        await asyncio.sleep(interval)
        gen = service.get_generation(generation_id)
        if gen is None or gen.status in _TERMINAL:
            break
        if is_video_advance_inflight(gen.id):
            continue  # 조회발 전진이 진행 중 — 이번 tick 은 건너뛴다
        try:
            await worker.advance_once(gen, provider)
        except Exception:  # noqa: BLE001
            service.fail_generation(gen, gen.generation_type, ErrorCode.GENERATION_FAILED)
            break
    else:
        gen = service.get_generation(generation_id)
        if gen is not None and gen.status not in _TERMINAL:
            service.fail_generation(gen, gen.generation_type, ErrorCode.GENERATION_FAILED)


def _storage_response() -> StudioStorageConfigResponse:
    s = get_settings()
    return StudioStorageConfigResponse(
        backend=s.asset_store_backend.upper(),
        storage_profile_name=s.studio_storage_profile_name,
        output_prefix=s.studio_output_prefix,
        output_retention_days=s.studio_output_retention_days,
    )


def _download_filename(project_id: str, mime_type: str) -> str:
    ext = _DOWNLOAD_EXTENSIONS.get(mime_type, "bin")
    return f"hairso-studio-{project_id[:8]}.{ext}"


def _script_schema(script: StudioScript) -> StudioScriptSchema:
    return StudioScriptSchema(hook=script.hook, narration=script.narration, cta=script.cta)


def _scene_schema(scene: StudioScene) -> StudioSceneSchema:
    return StudioSceneSchema(
        scene_index=scene.scene_index,
        duration_seconds=scene.duration_seconds,
        caption=scene.caption,
        visual_prompt=scene.visual_prompt,
    )


def _draft_schema(draft: StudioDraft | None) -> StudioDraftSchema | None:
    if draft is None:
        return None
    return StudioDraftSchema(
        version=draft.version,
        script=_script_schema(draft.script),
        storyboard=[_scene_schema(scene) for scene in draft.storyboard],
        updated_at=draft.updated_at,
    )


def _project_response(
    project: StudioProject,
    generation_service: GenerationService,
) -> StudioProjectResponse:
    render_status: GenerationStatus | None = None
    if project.render_generation_id:
        gen = generation_service.get_generation(project.render_generation_id)
        render_status = gen.status if gen is not None else None
    return StudioProjectResponse(
        project_id=project.id,
        template_type=project.template_type,
        category=project.category,
        status=project.status,
        title=project.title,
        offer_text=project.offer_text,
        cta_text=project.cta_text,
        duration_seconds=project.duration_seconds,
        target_audience=project.target_audience,
        tone=project.tone,
        asset_ids=project.asset_ids,
        logo_asset_id=project.logo_asset_id,
        disclaimer=project.disclaimer,
        draft=_draft_schema(project.draft),
        render_generation_id=project.render_generation_id,
        render_status=render_status,
        output_asset_id=project.output_asset_id,
        storage=_storage_response(),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _raise_http(exc: DomainError) -> None:
    if exc.error_code.value == "NOT_FOUND":
        status = 404
    elif exc.error_code.value == "FORBIDDEN":
        status = 403
    elif exc.error_code.value == "GENERATION_DUPLICATED":
        status = 409
    else:
        status = 400
    raise HTTPException(status_code=status, detail=exc.error_code.value) from exc


@router.post("/projects", status_code=201, response_model=StudioProjectResponse)
async def create_studio_project(
    request: StudioProjectCreateRequest,
    service: StudioServiceDep,
    generation_service: GenerationServiceDep,
    user_id: OptionalUserDep,
) -> StudioProjectResponse:
    """Studio 프로젝트 생성. 기본 템플릿은 PROMOTION_SHORT 이고 Hair 는 category 중 하나다."""
    settings = get_settings()
    try:
        project = service.create_project(
            project_id=str(uuid.uuid4()),
            template_type=request.template_type,
            category=request.category,
            title=request.title,
            offer_text=request.offer_text,
            cta_text=request.cta_text,
            duration_seconds=request.duration_seconds,
            target_audience=request.target_audience,
            tone=request.tone,
            asset_ids=request.asset_ids,
            logo_asset_id=request.logo_asset_id,
            disclaimer=request.disclaimer,
            created_by=user_id,
            storage_profile_name=settings.studio_storage_profile_name,
        )
    except DomainError as exc:
        _raise_http(exc)
    return _project_response(project, generation_service)


@router.get("/projects/{project_id}", response_model=StudioProjectResponse)
async def get_studio_project(
    project_id: str,
    service: StudioServiceDep,
    generation_service: GenerationServiceDep,
    asset_service: AssetServiceDep,
    user_id: OptionalUserDep,
) -> StudioProjectResponse:
    try:
        project = service.get_project(project_id, user_id)
    except DomainError as exc:
        _raise_http(exc)
    # BE 재시작으로 백그라운드 폴러가 사라졌어도 조회 폴링이 render 전진을 이어받는다.
    if project.render_generation_id:
        gen = generation_service.get_generation(project.render_generation_id)
        if gen is not None:
            advanced = await advance_stalled_video_generation(gen, generation_service, asset_service)
            if advanced is not None and advanced.status is not gen.status:
                project = service.get_project(project_id, user_id)  # _refresh_render_status 재반영
    return _project_response(project, generation_service)


@router.post("/projects/{project_id}/draft", response_model=StudioProjectResponse)
async def create_studio_draft(
    project_id: str,
    service: StudioServiceDep,
    generation_service: GenerationServiceDep,
    user_id: OptionalUserDep,
) -> StudioProjectResponse:
    try:
        project = service.create_draft(project_id, user_id)
    except DomainError as exc:
        _raise_http(exc)
    return _project_response(project, generation_service)


@router.patch("/projects/{project_id}/draft", response_model=StudioProjectResponse)
async def update_studio_draft(
    project_id: str,
    request: StudioDraftPatchRequest,
    service: StudioServiceDep,
    generation_service: GenerationServiceDep,
    user_id: OptionalUserDep,
) -> StudioProjectResponse:
    script = StudioScript(
        hook=request.script.hook,
        narration=list(request.script.narration),
        cta=request.script.cta,
    )
    storyboard = [
        StudioScene(
            scene_index=scene.scene_index,
            duration_seconds=scene.duration_seconds,
            caption=scene.caption,
            visual_prompt=scene.visual_prompt,
        )
        for scene in request.storyboard
    ]
    try:
        project = service.update_draft(project_id, script, storyboard, user_id)
    except DomainError as exc:
        _raise_http(exc)
    return _project_response(project, generation_service)


@router.post("/projects/{project_id}/render", status_code=202, response_model=StudioRenderResponse)
async def render_studio_project(
    project_id: str,
    request: StudioRenderRequest,
    background: BackgroundTasks,
    service: StudioServiceDep,
    generation_service: GenerationServiceDep,
    asset_service: AssetServiceDep,
    user_id: OptionalUserDep,
) -> StudioRenderResponse:
    provider = get_default_video_provider()
    generation_id = str(uuid.uuid4())
    try:
        _, gen = await service.render_project(
            project_id=project_id,
            generation_id=generation_id,
            idempotency_key=request.idempotency_key,
            provider=provider,
            created_by=user_id,
        )
    except DomainError as exc:
        _raise_http(exc)

    if gen.id == generation_id and gen.status is GenerationStatus.SUBMITTED:
        background.add_task(
            _advance_video_generation,
            gen.id,
            generation_service,
            asset_service,
            provider,
        )

    return StudioRenderResponse(
        project_id=project_id,
        generation_id=gen.id,
        status=gen.status,
    )


@router.get("/projects/{project_id}/download")
async def download_studio_project(
    project_id: str,
    service: StudioServiceDep,
    user_id: OptionalUserDep,
) -> Response:
    """Studio render 결과를 모바일 브라우저 다운로드로 내려준다."""
    try:
        data, mime_type = service.get_output_bytes(project_id, user_id)
    except DomainError as exc:
        _raise_http(exc)
    filename = _download_filename(project_id, mime_type)
    return Response(
        content=data,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
