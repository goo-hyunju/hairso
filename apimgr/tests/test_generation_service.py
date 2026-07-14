"""GenerationService 흐름·Idempotency·상태반영 테스트."""

import unittest

from app.domain.enums import GenerationStatus, GenerationType, ProviderJobStatus
from app.providers.video_generation.base import VideoGenerationInput
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.services.generation_service import GenerationService


def _input(key: str) -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="asset-1",
        prompt="turn head",
        duration_seconds=5,
        aspect_ratio="9:16",
        quality="720p",
        idempotency_key=key,
    )


class TestGenerationService(unittest.IsolatedAsyncioTestCase):
    async def test_submit_success_sets_submitted(self):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        gen = await svc.create_video_generation(
            "gen-1", "consult-1", _input("k1"), MockVideoProvider(MockScenario.SUCCESS)
        )
        self.assertEqual(gen.status, GenerationStatus.SUBMITTED)
        self.assertTrue(gen.external_job_id)

    async def test_submit_failure_sets_failed(self):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        gen = await svc.create_video_generation(
            "gen-2", "consult-1", _input("k2"), MockVideoProvider(MockScenario.RATE_LIMIT)
        )
        self.assertEqual(gen.status, GenerationStatus.FAILED)
        self.assertIsNotNone(gen.error_code)

    async def test_idempotent_resubmit_returns_same(self):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        g1 = await svc.create_video_generation(
            "gen-3", "consult-1", _input("dup"), MockVideoProvider(MockScenario.SUCCESS)
        )
        g2 = await svc.create_video_generation(
            "gen-4", "consult-1", _input("dup"), MockVideoProvider(MockScenario.SUCCESS)
        )
        self.assertEqual(g1.id, g2.id)  # 두 번째 요청은 새 작업을 만들지 않는다

    async def test_apply_status_noop_on_late_event(self):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        gen = await svc.create_video_generation(
            "gen-5", "consult-1", _input("k5"), MockVideoProvider(MockScenario.SUCCESS)
        )
        # 강제로 SUCCEEDED 상태로 만든 뒤 늦은 PROCESSING 이 와도 되돌지 않음
        gen.status = GenerationStatus.SUCCEEDED
        gen = svc.apply_provider_status(gen, ProviderJobStatus.PROCESSING, GenerationType.VIDEO)
        self.assertEqual(gen.status, GenerationStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
