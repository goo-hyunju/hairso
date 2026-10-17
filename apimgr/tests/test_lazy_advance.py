"""상태 조회발 lazy advance 회귀 — BE 재시작으로 백그라운드 폴러가 죽어도 조회가 전진을 이어받는다."""

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.api.v1.generations import advance_stalled_video_generation
from app.domain.enums import GenerationStatus, ProviderJobStatus
from app.providers.storage.local_disk import LocalDiskAssetStore
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoStatusResult,
    VideoSubmissionResult,
)
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.asset_repository import InMemoryAssetRepository
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService

_MP4_BYTES = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    b"\x00\x00\x00\x08free\x00\x00\x00\x08mdat"
)


def _input(key: str) -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="a1", prompt="p", duration_seconds=5,
        aspect_ratio="9:16", quality="480p", idempotency_key=key,
    )


class _CompletedRemoteProvider(VideoProvider):
    """ml 서버 job 이 이미 SUCCEEDED 인 상황을 흉내내는 비-Mock provider."""

    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        raise NotImplementedError("lazy advance 는 submit 을 호출하지 않는다")

    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        return VideoStatusResult(
            status=ProviderJobStatus.SUCCEEDED,
            output_bytes=_MP4_BYTES,
        )


class TestLazyAdvance(unittest.IsolatedAsyncioTestCase):
    async def _submitted_generation(self):
        svc = GenerationService(InMemoryGenerationRepository())
        gen = await svc.create_video_generation(
            "gen-1", "c1", _input("k1"), MockVideoProvider(MockScenario.SUCCESS)
        )
        return svc, gen

    async def test_stalled_video_completes_via_status_poll(self):
        # 폴러가 없는 상태(BE 재시작 시나리오)에서 조회 한 번으로 SUCCEEDED 까지 전진한다.
        svc, gen = await self._submitted_generation()
        self.assertEqual(gen.status, GenerationStatus.SUBMITTED)
        with TemporaryDirectory() as tmp:
            asset_service = AssetService(
                LocalDiskAssetStore(tmp),
                InMemoryAssetRepository(),
                generated_video_prefix="studio/test-outputs",
            )
            with patch(
                "app.api.v1.generations.get_default_video_provider",
                return_value=_CompletedRemoteProvider(),
            ):
                advanced = await advance_stalled_video_generation(gen, svc, asset_service)
        self.assertEqual(advanced.status, GenerationStatus.SUCCEEDED)
        self.assertIsNotNone(advanced.output_asset_id)
        self.assertEqual(svc._repo.get(gen.id).status, GenerationStatus.SUCCEEDED)

    async def test_terminal_generation_is_untouched(self):
        svc, gen = await self._submitted_generation()
        gen.status = GenerationStatus.SUCCEEDED
        with patch("app.api.v1.generations.get_default_video_provider") as provider_factory:
            advanced = await advance_stalled_video_generation(gen, svc, None)
        provider_factory.assert_not_called()
        self.assertIs(advanced, gen)

    async def test_mock_provider_is_skipped(self):
        # Mock 은 인스턴스 내부 상태라 조회발 전진 대상이 아니다(데모 폴러 담당).
        svc, gen = await self._submitted_generation()
        with patch(
            "app.api.v1.generations.get_default_video_provider",
            return_value=MockVideoProvider(MockScenario.SUCCESS),
        ):
            advanced = await advance_stalled_video_generation(gen, svc, None)
        self.assertEqual(advanced.status, GenerationStatus.SUBMITTED)

    async def test_provider_error_keeps_current_status(self):
        # 전진 실패는 조회 실패가 아니다 — 상태를 그대로 반환하고 다음 폴링이 재시도한다.
        svc, gen = await self._submitted_generation()

        class _BrokenProvider(_CompletedRemoteProvider):
            async def get_status(self, external_job_id: str) -> VideoStatusResult:
                raise RuntimeError("ml server unreachable")

        with patch(
            "app.api.v1.generations.get_default_video_provider",
            return_value=_BrokenProvider(),
        ):
            advanced = await advance_stalled_video_generation(gen, svc, None)
        self.assertEqual(advanced.status, GenerationStatus.SUBMITTED)


if __name__ == "__main__":
    unittest.main()
