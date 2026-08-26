"""Studio 제품 계층 서비스.

Studio 는 script/storyboard/edit/render 흐름을 관리하고, 실제 생성 상태는 기존 GenerationService 를
재사용한다. 외부 AI Provider 호출은 여전히 backend-owned 이며 FE 로 노출하지 않는다.
"""

from __future__ import annotations

from app.domain.enums import (
    ErrorCode,
    GenerationStatus,
    StudioCategory,
    StudioProjectStatus,
    StudioTemplateType,
    StudioTone,
)
from app.domain.errors import DomainError
from app.domain.models import Asset, _utcnow
from app.domain.studio import StudioDraft, StudioProject, StudioScene, StudioScript
from app.providers.studio_draft.base import (
    StudioDraftInput,
    StudioDraftProvider,
    StudioDraftProviderError,
)
from app.providers.studio_draft.mock import MockStudioDraftProvider
from app.providers.studio_draft.safety import SensitiveTextError, assert_safe_draft_text
from app.providers.video_generation.base import VideoGenerationInput, VideoProvider, VideoSourceImage
from app.repositories.studio_repository import StudioRepository
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService


class StudioProjectNotFound(DomainError):
    error_code = ErrorCode.NOT_FOUND
    retryable = False


class StudioDraftRequired(DomainError):
    error_code = ErrorCode.VALIDATION_ERROR
    retryable = False


class StudioProjectForbidden(DomainError):
    error_code = ErrorCode.FORBIDDEN
    retryable = False


class StudioUnsafeText(DomainError):
    error_code = ErrorCode.VALIDATION_ERROR
    retryable = False


_STUDIO_INPUT_ASSET_TYPES = {"FACE_SOURCE", "GENERATED_IMAGE"}


class StudioService:
    def __init__(
        self,
        repo: StudioRepository,
        generation_service: GenerationService,
        asset_service: AssetService,
        draft_provider: StudioDraftProvider | None = None,
    ) -> None:
        self._repo = repo
        self._generation_service = generation_service
        self._asset_service = asset_service
        self._draft_provider = draft_provider or MockStudioDraftProvider()
        self._fallback_draft_provider = MockStudioDraftProvider()

    def create_project(
        self,
        *,
        project_id: str,
        template_type: StudioTemplateType,
        category: StudioCategory,
        title: str,
        offer_text: str,
        cta_text: str,
        duration_seconds: int,
        target_audience: str | None,
        tone: StudioTone,
        asset_ids: list[str],
        logo_asset_id: str | None,
        disclaimer: str | None,
        created_by: str | None,
        storage_profile_name: str,
    ) -> StudioProject:
        self._assert_project_text_safe(title, offer_text, cta_text, target_audience, disclaimer)
        self._assert_asset_references(asset_ids, logo_asset_id, created_by)
        project = StudioProject(
            id=project_id,
            template_type=template_type,
            category=category,
            title=title.strip(),
            offer_text=offer_text.strip(),
            cta_text=cta_text.strip(),
            duration_seconds=duration_seconds,
            target_audience=target_audience.strip() if target_audience else None,
            tone=tone,
            asset_ids=list(asset_ids),
            logo_asset_id=logo_asset_id,
            disclaimer=disclaimer.strip() if disclaimer else None,
            created_by=created_by,
            storage_profile_name=storage_profile_name,
        )
        return self._repo.save(project)

    def get_project(self, project_id: str, user_id: str | None = None) -> StudioProject:
        project = self._repo.get(project_id)
        if project is None:
            raise StudioProjectNotFound()
        self._assert_can_access(project, user_id)
        return self._refresh_render_status(project)

    def create_draft(self, project_id: str, user_id: str | None = None) -> StudioProject:
        project = self.get_project(project_id, user_id)
        self._assert_project_text_safe(
            project.title,
            project.offer_text,
            project.cta_text,
            project.target_audience,
            project.disclaimer,
        )
        draft_input = self._draft_input(project)
        project.draft = self._create_provider_draft(draft_input)
        project.status = StudioProjectStatus.DRAFT_READY
        project.updated_at = _utcnow()
        return self._repo.update(project)

    def update_draft(
        self,
        project_id: str,
        script: StudioScript,
        storyboard: list[StudioScene],
        user_id: str | None = None,
    ) -> StudioProject:
        project = self.get_project(project_id, user_id)
        self._assert_draft_text_safe(script, storyboard)
        current_version = project.draft.version if project.draft is not None else 0
        project.draft = StudioDraft(
            script=script,
            storyboard=storyboard,
            version=current_version + 1,
        )
        project.status = StudioProjectStatus.DRAFT_READY
        project.updated_at = _utcnow()
        return self._repo.update(project)

    async def render_project(
        self,
        *,
        project_id: str,
        generation_id: str,
        idempotency_key: str,
        provider: VideoProvider,
        created_by: str | None,
    ):
        project = self.get_project(project_id, created_by)
        if project.draft is None:
            raise StudioDraftRequired("초안 생성 후 render 할 수 있습니다")
        self._assert_draft_text_safe(project.draft.script, project.draft.storyboard)

        if project.render_generation_id:
            existing = self._generation_service.get_generation(project.render_generation_id)
            if existing is not None:
                return project, existing

        input_data = VideoGenerationInput(
            image_asset_id=self._select_render_input_asset(project),
            prompt=self._build_render_prompt(project),
            duration_seconds=5,
            aspect_ratio="9:16",
            quality="720p",
            idempotency_key=idempotency_key,
            negative_prompt=None,
            seed=None,
            source_image=self._select_render_source_image(project, created_by),
        )
        gen = await self._generation_service.create_video_generation(
            generation_id=generation_id,
            consultation_id=project.id,
            input_data=input_data,
            provider=provider,
            created_by=created_by,
        )
        project.render_generation_id = gen.id
        project.status = StudioProjectStatus.RENDERING
        project.updated_at = _utcnow()
        project = self._repo.update(project)
        return project, gen

    def _refresh_render_status(self, project: StudioProject) -> StudioProject:
        if not project.render_generation_id:
            return project
        gen = self._generation_service.get_generation(project.render_generation_id)
        if gen is None:
            return project
        next_status = project.status
        if gen.status is GenerationStatus.SUCCEEDED:
            next_status = StudioProjectStatus.SUCCEEDED
            project.output_asset_id = gen.output_asset_id
        elif gen.status in {GenerationStatus.FAILED, GenerationStatus.CANCELED, GenerationStatus.EXPIRED}:
            next_status = StudioProjectStatus.FAILED
        else:
            next_status = StudioProjectStatus.RENDERING
        if next_status is not project.status:
            project.status = next_status
            project.updated_at = _utcnow()
            project = self._repo.update(project)
        elif gen.output_asset_id and gen.output_asset_id != project.output_asset_id:
            project.output_asset_id = gen.output_asset_id
            project.updated_at = _utcnow()
            project = self._repo.update(project)
        return project

    def _assert_can_access(self, project: StudioProject, user_id: str | None) -> None:
        if project.created_by is not None and project.created_by != user_id:
            raise StudioProjectForbidden()

    def _assert_asset_references(
        self,
        asset_ids: list[str],
        logo_asset_id: str | None,
        user_id: str | None,
    ) -> None:
        for asset_id in asset_ids:
            asset = self._asset_service.assert_reference_allowed(
                asset_id,
                user_id,
                _STUDIO_INPUT_ASSET_TYPES,
            )
            self._assert_studio_asset_owner_allowed(asset)
        if logo_asset_id:
            asset = self._asset_service.assert_reference_allowed(
                logo_asset_id,
                user_id,
                _STUDIO_INPUT_ASSET_TYPES,
            )
            self._assert_studio_asset_owner_allowed(asset)

    def _create_provider_draft(self, draft_input: StudioDraftInput) -> StudioDraft:
        try:
            draft = self._draft_provider.create_draft(draft_input)
            self._assert_draft_text_safe(draft.script, draft.storyboard)
            return draft
        except (StudioDraftProviderError, StudioUnsafeText):
            fallback = self._fallback_draft_provider.create_draft(draft_input)
            self._assert_draft_text_safe(fallback.script, fallback.storyboard)
            return fallback

    def _assert_studio_asset_owner_allowed(self, asset: Asset) -> None:
        if asset.asset_type == "GENERATED_IMAGE" and asset.owner_id is None:
            raise StudioProjectForbidden("소유자 없는 생성 결과는 Studio 입력으로 사용할 수 없습니다")

    def _assert_project_text_safe(
        self,
        title: str,
        offer_text: str,
        cta_text: str,
        target_audience: str | None,
        disclaimer: str | None,
    ) -> None:
        fields = {
            "title": title,
            "offer_text": offer_text,
            "cta_text": cta_text,
            "target_audience": target_audience,
            "disclaimer": disclaimer,
        }
        for field_name, value in fields.items():
            self._assert_text_safe(value, field_name)

    def _assert_draft_text_safe(self, script: StudioScript, storyboard: list[StudioScene]) -> None:
        self._assert_text_safe(script.hook, "script.hook")
        self._assert_text_safe(script.cta, "script.cta")
        for index, line in enumerate(script.narration, start=1):
            self._assert_text_safe(line, f"script.narration[{index}]")
        for scene in storyboard:
            self._assert_text_safe(scene.caption, f"storyboard[{scene.scene_index}].caption")
            self._assert_text_safe(
                scene.visual_prompt,
                f"storyboard[{scene.scene_index}].visual_prompt",
            )

    def _assert_text_safe(self, value: str | None, field_name: str) -> None:
        try:
            assert_safe_draft_text(value, field_name)
        except SensitiveTextError as exc:
            raise StudioUnsafeText("Studio draft text contains a sensitive media reference") from exc

    def _draft_input(self, project: StudioProject) -> StudioDraftInput:
        if project.template_type not in {
            StudioTemplateType.PROMOTION_SHORT,
            StudioTemplateType.SALON_EVENT_PROMOTION,
        }:
            raise StudioDraftRequired("지원하지 않는 템플릿입니다")
        return StudioDraftInput(
            template_type=project.template_type,
            category=project.category,
            title=project.title,
            offer_text=project.offer_text,
            cta_text=project.cta_text,
            duration_seconds=project.duration_seconds,
            target_audience=project.target_audience,
            tone=project.tone,
            asset_count=len(project.asset_ids),
            has_logo=project.logo_asset_id is not None,
            disclaimer=project.disclaimer,
        )

    def _build_render_prompt(self, project: StudioProject) -> str:
        if project.draft is None:
            raise StudioDraftRequired("초안 생성 후 render 할 수 있습니다")
        captions = " / ".join(scene.caption for scene in project.draft.storyboard)
        narration = " ".join(project.draft.script.narration)
        return (
            f"[{project.template_type.value}] {project.draft.script.hook} "
            f"{narration} CTA: {project.draft.script.cta}. Scenes: {captions}"
        )

    def _select_render_input_asset(self, project: StudioProject) -> str | None:
        if project.logo_asset_id:
            return project.logo_asset_id
        if project.asset_ids:
            return project.asset_ids[0]
        return None

    def _select_render_source_image(
        self, project: StudioProject, user_id: str | None
    ) -> VideoSourceImage | None:
        asset_id = self._select_render_input_asset(project)
        if asset_id is None:
            return None
        data, content_type = self._asset_service.load_reference_bytes(
            asset_id,
            user_id,
            _STUDIO_INPUT_ASSET_TYPES,
        )
        return VideoSourceImage(data=data, content_type=content_type)
