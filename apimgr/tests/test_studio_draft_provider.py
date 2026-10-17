"""Studio draft provider 테스트 — 외부 네트워크 없이 Mock/Ollama 구조 검증."""

import json
import unittest
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from app.domain.enums import (
    ProviderJobStatus,
    ProviderName,
    StudioCategory,
    StudioProjectStatus,
    StudioTemplateType,
    StudioTone,
)
from app.domain.models import Asset
from app.domain.studio import StudioDraft, StudioProject, StudioScene, StudioScript
from app.providers.studio_draft.base import (
    StudioDraftInput,
    StudioDraftProvider,
    StudioDraftProviderError,
)
from app.providers.studio_draft.mock import MockStudioDraftProvider
from app.providers.studio_draft.ollama import OllamaStudioDraftProvider
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoStatusResult,
    VideoSubmissionResult,
)
from app.providers.video_generation.mock import MockVideoProvider
from app.repositories.asset_repository import InMemoryAssetRepository
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.repositories.studio_repository import InMemoryStudioRepository
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService
from app.services.studio_service import (
    StudioProjectForbidden,
    StudioRenderAssetRequired,
    StudioService,
    StudioUnsafeText,
)


def _input(duration_seconds: int = 30) -> StudioDraftInput:
    return StudioDraftInput(
        template_type=StudioTemplateType.PROMOTION_SHORT,
        category=StudioCategory.HAIR,
        title="여름 신상 레이어드컷",
        offer_text="이번 주 가능한 스타일 상담 안내",
        cta_text="프로필 링크에서 지금 예약하세요",
        duration_seconds=duration_seconds,
        target_audience="국내 미용실 고객",
        tone=StudioTone.TRENDY,
        asset_count=1,
        has_logo=False,
        disclaimer=None,
    )


class _Response:
    def __init__(self, content: dict[str, Any]) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._content


class _Client:
    last_payload: dict[str, Any] | None = None

    def __init__(self, *args, **kwargs) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]):
        _Client.last_payload = json
        draft = {
            "version": 1,
            "script": {
                "hook": "지금 이 컷, 왜 다들 예약할까요?",
                "narration": [
                    "이번 여름 신상, 얼굴형 살리는 레이어드컷.",
                    "이번 주 가능한 스타일 상담을 안내합니다.",
                ],
                "cta": "프로필 링크에서 지금 예약하세요",
            },
            "storyboard": [
                {
                    "scene_index": 1,
                    "duration_seconds": 5,
                    "caption": "여름 신상 레이어드컷",
                    "visual_prompt": "Photorealistic salon close-up, slow push-in, 9:16",
                },
                {
                    "scene_index": 2,
                    "duration_seconds": 6,
                    "caption": "얼굴형은 살리고",
                    "visual_prompt": "Medium shot, gentle turn, natural hair flow, 9:16",
                },
                {
                    "scene_index": 3,
                    "duration_seconds": 6,
                    "caption": "아침이 편해지는 스타일",
                    "visual_prompt": "Detail shot of hair ends bouncing lightly, 9:16",
                },
                {
                    "scene_index": 4,
                    "duration_seconds": 8,
                    "caption": "비포 애프터",
                    "visual_prompt": "Smooth before after transition, same face, 9:16",
                },
                {
                    "scene_index": 5,
                    "duration_seconds": 5,
                    "caption": "스타일 상담 안내",
                    "visual_prompt": "Clear call-to-action end card, typography-safe, 9:16",
                },
            ],
        }
        return _Response({"response": json_module.dumps(draft)})


class _UnsafeOutputClient(_Client):
    def post(self, url: str, json: dict[str, Any]):
        draft = {
            "version": 1,
            "script": {
                "hook": "https://example.invalid/signed.png",
                "narration": ["안전하지 않은 초안입니다."],
                "cta": "예약 문의",
            },
            "storyboard": [
                {
                    "scene_index": 1,
                    "duration_seconds": 5,
                    "caption": "자막",
                    "visual_prompt": "data:image/png;base64,abcdef",
                },
                {
                    "scene_index": 2,
                    "duration_seconds": 5,
                    "caption": "안내",
                    "visual_prompt": "Photorealistic salon scene, 9:16",
                },
                {
                    "scene_index": 3,
                    "duration_seconds": 5,
                    "caption": "예약 문의",
                    "visual_prompt": "Clear CTA end card, 9:16",
                },
            ],
        }
        return _Response({"response": json_module.dumps(draft)})


json_module = json


class _FailingDraftProvider(StudioDraftProvider):
    def create_draft(self, data: StudioDraftInput):
        raise StudioDraftProviderError("boom")


class _UnsafeDraftProvider(StudioDraftProvider):
    def create_draft(self, data: StudioDraftInput):
        return StudioDraft(
            script=StudioScript(
                hook="https://example.invalid/signed.png",
                narration=["안전하지 않은 provider 출력입니다."],
                cta=data.cta_text,
            ),
            storyboard=[
                StudioScene(
                    scene_index=1,
                    duration_seconds=5,
                    caption=data.title,
                    visual_prompt="data:image/png;base64,abcdef",
                ),
                StudioScene(
                    scene_index=2,
                    duration_seconds=5,
                    caption=data.offer_text,
                    visual_prompt="Photorealistic salon scene, 9:16",
                ),
                StudioScene(
                    scene_index=3,
                    duration_seconds=5,
                    caption=data.cta_text,
                    visual_prompt="Clear CTA end card, 9:16",
                ),
            ],
        )


class _RecordingVideoProvider(MockVideoProvider):
    def __init__(self) -> None:
        super().__init__()
        self.last_input: VideoGenerationInput | None = None

    async def submit(self, data: VideoGenerationInput):
        self.last_input = data
        return await super().submit(data)


class _RecordingRealVideoProvider(VideoProvider):
    def __init__(self) -> None:
        self.last_input: VideoGenerationInput | None = None

    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        self.last_input = data
        return VideoSubmissionResult(
            provider=ProviderName.SELF_HOSTED_WAN,
            external_job_id=f"real-video-{data.idempotency_key}",
        )

    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        return VideoStatusResult(status=ProviderJobStatus.PROCESSING)


class TestStudioDraftProvider(unittest.TestCase):
    def test_mock_5_second_draft_uses_one_scene(self):
        draft = MockStudioDraftProvider().create_draft(_input(5))
        self.assertEqual([scene.duration_seconds for scene in draft.storyboard], [5])
        self.assertEqual(sum(scene.duration_seconds for scene in draft.storyboard), 5)
        self.assertTrue(all("9:16" in scene.visual_prompt for scene in draft.storyboard))

    def test_mock_30_second_draft_uses_clip_safe_durations(self):
        draft = MockStudioDraftProvider().create_draft(_input(30))
        self.assertEqual([scene.duration_seconds for scene in draft.storyboard], [5, 6, 6, 8, 5])
        self.assertEqual(sum(scene.duration_seconds for scene in draft.storyboard), 30)
        self.assertTrue(all("9:16" in scene.visual_prompt for scene in draft.storyboard))

    def test_mock_free_i2v_draft_uses_general_motion_prompt(self):
        draft = MockStudioDraftProvider().create_draft(
            StudioDraftInput(
                template_type=StudioTemplateType.FREE_IMAGE_TO_VIDEO,
                category=StudioCategory.PET,
                title="고양이가 밥 먹는 장면",
                offer_text="A cute cat eating food from a small bowl",
                cta_text="Cozy pet moment",
                duration_seconds=15,
                target_audience="반려동물 일상 영상",
                tone=StudioTone.FRIENDLY,
                asset_count=1,
                has_logo=False,
                disclaimer="Keep the cat identity and markings consistent.",
            )
        )

        self.assertEqual(draft.script.hook, "고양이가 밥 먹는 장면")
        self.assertEqual(len(draft.storyboard), 1)
        self.assertEqual(draft.storyboard[0].duration_seconds, 5)
        self.assertIn("cat", draft.storyboard[0].visual_prompt)
        self.assertIn("pet", draft.storyboard[0].visual_prompt.lower())

    def test_mock_hair_styling_draft_uses_natural_motion_prompt(self):
        draft = MockStudioDraftProvider().create_draft(
            StudioDraftInput(
                template_type=StudioTemplateType.HAIR_STYLING_MOTION,
                category=StudioCategory.HAIR,
                title="자연스러운 헤어 스타일링",
                offer_text="부드러운 고개 움직임과 자연스러운 모발 결 흔들림",
                cta_text="Natural styling look",
                duration_seconds=15,
                target_audience="자연스러운 헤어 연출",
                tone=StudioTone.CALM,
                asset_count=1,
                has_logo=False,
                disclaimer="얼굴, 헤어 라인, 기존 모발 색은 유지합니다.",
            )
        )

        self.assertEqual(draft.script.hook, "자연스러운 헤어 스타일링")
        self.assertEqual(len(draft.storyboard), 1)
        self.assertEqual(draft.storyboard[0].duration_seconds, 5)
        self.assertIn("hair styling", draft.storyboard[0].visual_prompt.lower())
        self.assertIn("face identity", draft.storyboard[0].visual_prompt.lower())
        self.assertNotIn("coupon", draft.storyboard[0].visual_prompt.lower())

    def test_ollama_provider_parses_structured_response_without_media_payload(self):
        with patch("app.providers.studio_draft.ollama.httpx.Client", _Client):
            draft = OllamaStudioDraftProvider(
                "http://127.0.0.1:11434",
                "test-local-model",
            ).create_draft(_input(30))

        self.assertEqual(draft.script.hook, "지금 이 컷, 왜 다들 예약할까요?")
        self.assertEqual(len(draft.storyboard), 5)
        self.assertEqual(sum(scene.duration_seconds for scene in draft.storyboard), 30)
        self.assertIsNotNone(_Client.last_payload)
        self.assertNotIn("images", _Client.last_payload)
        prompt_text = str(_Client.last_payload["prompt"])
        self.assertNotIn("data:image", prompt_text)
        self.assertNotIn("storage_key", prompt_text)

    def test_ollama_provider_rejects_non_local_base_url(self):
        with self.assertRaises(StudioDraftProviderError):
            OllamaStudioDraftProvider("https://example.com", "test-local-model")

    def test_ollama_provider_rejects_sensitive_input_text(self):
        with self.assertRaises(StudioDraftProviderError):
            OllamaStudioDraftProvider(
                "http://127.0.0.1:11434",
                "test-local-model",
            ).create_draft(replace(_input(30), offer_text="결과 https://example.com/signed.png"))

    def test_ollama_provider_rejects_sensitive_output_text(self):
        with (
            patch("app.providers.studio_draft.ollama.httpx.Client", _UnsafeOutputClient),
            self.assertRaises(StudioDraftProviderError),
        ):
            OllamaStudioDraftProvider(
                "http://127.0.0.1:11434",
                "test-local-model",
            ).create_draft(_input(15))

    def test_studio_service_falls_back_to_mock_draft_when_provider_fails(self):
        svc = StudioService(
            InMemoryStudioRepository(),
            GenerationService(InMemoryGenerationRepository()),
            object(),
            _FailingDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-fallback-1",
            template_type=StudioTemplateType.PROMOTION_SHORT,
            category=StudioCategory.HAIR,
            title="봄맞이 헤어 클리닉 안내",
            offer_text="손상 모발 집중 케어 안내",
            cta_text="오늘 예약 문의하기",
            duration_seconds=15,
            target_audience="신규 고객",
            tone=StudioTone.FRIENDLY,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer=None,
            created_by=None,
            storage_profile_name="local-dev",
        )

        drafted = svc.create_draft(project.id)

        self.assertEqual(drafted.status, StudioProjectStatus.DRAFT_READY)
        self.assertIsNotNone(drafted.draft)
        self.assertEqual(sum(scene.duration_seconds for scene in drafted.draft.storyboard), 15)

    def test_studio_service_falls_back_when_provider_returns_unsafe_draft(self):
        svc = StudioService(
            InMemoryStudioRepository(),
            GenerationService(InMemoryGenerationRepository()),
            object(),
            _UnsafeDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-unsafe-provider-1",
            template_type=StudioTemplateType.PROMOTION_SHORT,
            category=StudioCategory.HAIR,
            title="봄맞이 헤어 클리닉 안내",
            offer_text="손상 모발 집중 케어 안내",
            cta_text="오늘 예약 문의하기",
            duration_seconds=15,
            target_audience="신규 고객",
            tone=StudioTone.FRIENDLY,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer=None,
            created_by=None,
            storage_profile_name="local-dev",
        )

        drafted = svc.create_draft(project.id)

        self.assertIsNotNone(drafted.draft)
        self.assertNotIn("https://", drafted.draft.script.hook)
        self.assertNotIn("data:image", drafted.draft.storyboard[0].visual_prompt)

    def test_studio_service_rejects_ownerless_generated_image_reference(self):
        asset_repo = InMemoryAssetRepository()
        asset_repo.save(
            Asset(
                id="generated-image-asset",
                owner_type="SYSTEM",
                asset_type="GENERATED_IMAGE",
                storage_key="generated/result.png",
                mime_type="image/png",
                byte_size=1,
                owner_id=None,
            )
        )
        svc = StudioService(
            InMemoryStudioRepository(),
            GenerationService(InMemoryGenerationRepository()),
            AssetService(object(), asset_repo),
        )

        with self.assertRaises(StudioProjectForbidden):
            svc.create_project(
                project_id="studio-ownerless-1",
                template_type=StudioTemplateType.PROMOTION_SHORT,
                category=StudioCategory.HAIR,
                title="봄맞이 헤어 클리닉 안내",
                offer_text="손상 모발 집중 케어 안내",
                cta_text="오늘 예약 문의하기",
                duration_seconds=15,
                target_audience="신규 고객",
                tone=StudioTone.FRIENDLY,
                asset_ids=["generated-image-asset"],
                logo_asset_id=None,
                disclaimer=None,
                created_by="user-1",
                storage_profile_name="local-dev",
            )

    def test_studio_service_revalidates_existing_project_text_before_draft(self):
        repo = InMemoryStudioRepository()
        repo.save(
            StudioProject(
                id="studio-legacy-sensitive-1",
                template_type=StudioTemplateType.PROMOTION_SHORT,
                category=StudioCategory.HAIR,
                title="봄맞이 클리닉 이벤트",
                offer_text="기존 데이터 https://example.com/signed.png",
                cta_text="오늘 예약 문의하기",
                duration_seconds=15,
            )
        )
        svc = StudioService(
            repo,
            GenerationService(InMemoryGenerationRepository()),
            object(),
            MockStudioDraftProvider(),
        )

        with self.assertRaises(StudioUnsafeText):
            svc.create_draft("studio-legacy-sensitive-1")


class TestStudioRenderContracts(unittest.IsolatedAsyncioTestCase):
    async def test_render_without_asset_stores_nullable_input_asset(self):
        generation_service = GenerationService(InMemoryGenerationRepository())
        svc = StudioService(
            InMemoryStudioRepository(),
            generation_service,
            object(),
            MockStudioDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-render-no-asset-1",
            template_type=StudioTemplateType.PROMOTION_SHORT,
            category=StudioCategory.HAIR,
            title="봄맞이 헤어 클리닉 안내",
            offer_text="손상 모발 집중 케어 안내",
            cta_text="오늘 예약 문의하기",
            duration_seconds=15,
            target_audience="신규 고객",
            tone=StudioTone.FRIENDLY,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer=None,
            created_by=None,
            storage_profile_name="local-dev",
        )
        svc.create_draft(project.id)

        provider = _RecordingVideoProvider()
        _, generation = await svc.render_project(
            project_id=project.id,
            generation_id="11111111-1111-4111-8111-111111111111",
            idempotency_key="studio-render-no-asset",
            provider=provider,
            created_by=None,
        )

        self.assertIsNone(generation.input_asset_id)
        self.assertIsNotNone(provider.last_input)
        self.assertIsNone(provider.last_input.image_asset_id)
        self.assertEqual(provider.last_input.duration_seconds, 15)

    async def test_free_i2v_render_prompt_uses_motion_description(self):
        generation_service = GenerationService(InMemoryGenerationRepository())
        svc = StudioService(
            InMemoryStudioRepository(),
            generation_service,
            object(),
            MockStudioDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-render-free-i2v-1",
            template_type=StudioTemplateType.FREE_IMAGE_TO_VIDEO,
            category=StudioCategory.PET,
            title="고양이가 밥 먹는 장면",
            offer_text="A cute cat eating food from a small bowl",
            cta_text="Cozy pet moment",
            duration_seconds=15,
            target_audience="반려동물 일상 영상",
            tone=StudioTone.FRIENDLY,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer="Keep the cat identity and markings consistent.",
            created_by=None,
            storage_profile_name="local-dev",
        )
        svc.create_draft(project.id)

        provider = _RecordingVideoProvider()
        await svc.render_project(
            project_id=project.id,
            generation_id="44444444-4444-4444-8444-444444444444",
            idempotency_key="studio-render-free-i2v",
            provider=provider,
            created_by=None,
        )

        self.assertIsNotNone(provider.last_input)
        self.assertEqual(provider.last_input.duration_seconds, 15)
        self.assertIn("[FREE_IMAGE_TO_VIDEO]", provider.last_input.prompt)
        self.assertIn("A cute cat eating food from a small bowl", provider.last_input.prompt)

    async def test_hair_styling_render_prompt_preserves_identity(self):
        generation_service = GenerationService(InMemoryGenerationRepository())
        svc = StudioService(
            InMemoryStudioRepository(),
            generation_service,
            object(),
            MockStudioDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-render-hair-motion-1",
            template_type=StudioTemplateType.HAIR_STYLING_MOTION,
            category=StudioCategory.HAIR,
            title="자연스러운 헤어 스타일링",
            offer_text="부드러운 고개 움직임과 자연스러운 모발 결 흔들림",
            cta_text="Natural styling look",
            duration_seconds=15,
            target_audience="자연스러운 헤어 연출",
            tone=StudioTone.CALM,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer="얼굴, 헤어 라인, 기존 모발 색은 유지합니다.",
            created_by=None,
            storage_profile_name="local-dev",
        )
        svc.create_draft(project.id)

        provider = _RecordingVideoProvider()
        await svc.render_project(
            project_id=project.id,
            generation_id="55555555-5555-4555-8555-555555555555",
            idempotency_key="studio-render-hair-motion",
            provider=provider,
            created_by=None,
        )

        self.assertIsNotNone(provider.last_input)
        self.assertEqual(provider.last_input.duration_seconds, 15)
        self.assertIn("[HAIR_STYLING_MOTION]", provider.last_input.prompt)
        self.assertIn("Preserve face identity", provider.last_input.prompt)
        self.assertIn("subtle hair movement", provider.last_input.prompt)
        self.assertNotIn("coupon", provider.last_input.prompt.lower())

    async def test_render_without_asset_rejected_for_real_video_provider(self):
        generation_service = GenerationService(InMemoryGenerationRepository())
        svc = StudioService(
            InMemoryStudioRepository(),
            generation_service,
            object(),
            MockStudioDraftProvider(),
        )
        project = svc.create_project(
            project_id="studio-render-real-no-asset-1",
            template_type=StudioTemplateType.PROMOTION_SHORT,
            category=StudioCategory.HAIR,
            title="봄맞이 헤어 클리닉 안내",
            offer_text="손상 모발 집중 케어 안내",
            cta_text="오늘 예약 문의하기",
            duration_seconds=15,
            target_audience="신규 고객",
            tone=StudioTone.FRIENDLY,
            asset_ids=[],
            logo_asset_id=None,
            disclaimer=None,
            created_by=None,
            storage_profile_name="local-dev",
        )
        svc.create_draft(project.id)

        provider = _RecordingRealVideoProvider()
        with self.assertRaises(StudioRenderAssetRequired):
            await svc.render_project(
                project_id=project.id,
                generation_id="33333333-3333-4333-8333-333333333333",
                idempotency_key="studio-render-real-no-asset",
                provider=provider,
                created_by=None,
            )
        self.assertIsNone(provider.last_input)

    async def test_render_revalidates_legacy_unsafe_draft(self):
        repo = InMemoryStudioRepository()
        repo.save(
            StudioProject(
                id="studio-legacy-unsafe-render-1",
                template_type=StudioTemplateType.PROMOTION_SHORT,
                category=StudioCategory.HAIR,
                title="봄맞이 헤어 클리닉 안내",
                offer_text="손상 모발 집중 케어 안내",
                cta_text="오늘 예약 문의하기",
                duration_seconds=15,
                draft=StudioDraft(
                    script=StudioScript(
                        hook="이번 주 안내",
                        narration=["상세 https://example.invalid/signed.png"],
                        cta="오늘 예약 문의하기",
                    ),
                    storyboard=[
                        StudioScene(
                            scene_index=1,
                            duration_seconds=5,
                            caption="token=abc",
                            visual_prompt="Photorealistic salon scene, 9:16",
                        )
                    ],
                ),
            )
        )
        provider = _RecordingVideoProvider()
        svc = StudioService(
            repo,
            GenerationService(InMemoryGenerationRepository()),
            object(),
            MockStudioDraftProvider(),
        )

        with self.assertRaises(StudioUnsafeText):
            await svc.render_project(
                project_id="studio-legacy-unsafe-render-1",
                generation_id="22222222-2222-4222-8222-222222222222",
                idempotency_key="studio-legacy-unsafe-render",
                provider=provider,
                created_by=None,
            )
        self.assertIsNone(provider.last_input)


if __name__ == "__main__":
    unittest.main()
