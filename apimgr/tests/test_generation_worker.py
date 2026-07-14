"""GenerationWorker 상태 전진·실패 처리 테스트 (결함2·3 회귀 방지)."""

import unittest

from app.domain.enums import ErrorCode, GenerationStatus, GenerationType
from app.providers.video_generation.base import VideoGenerationInput
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.services.generation_service import GenerationService
from app.workers.generation_worker import GenerationWorker


def _input(key: str) -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="a1", prompt="p", duration_seconds=5,
        aspect_ratio="9:16", quality="720p", idempotency_key=key,
    )


class TestGenerationWorker(unittest.IsolatedAsyncioTestCase):
    async def _submit(self, scenario_provider):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        gen = await svc.create_video_generation(
            "gen-1", "c1", _input("k1"), MockVideoProvider(MockScenario.SUCCESS)
        )
        return svc, GenerationWorker(svc), gen

    async def test_async_fail_preserves_error_code(self):
        # 결함2 회귀: provider FAILED 시 gen.error_code 가 보존돼야 한다.
        svc, worker, gen = await self._submit(None)
        gen = await worker.advance_once(gen, MockVideoProvider(MockScenario.ASYNC_FAIL))
        self.assertEqual(gen.status, GenerationStatus.FAILED)
        self.assertEqual(gen.error_code, ErrorCode.GENERATION_FAILED)

    async def test_download_fail_sets_failed_with_code(self):
        # 결함3 회귀: 다운로드 실패는 FAILED(DOWNLOAD_FAILED) + repo 영속.
        svc, worker, gen = await self._submit(None)
        gen.status = GenerationStatus.PROCESSING  # 이전 폴링으로 진행됐다고 가정
        provider = MockVideoProvider(MockScenario.DOWNLOAD_FAIL, processing_polls=0)
        gen = await worker.advance_once(gen, provider)
        self.assertEqual(gen.status, GenerationStatus.FAILED)
        self.assertEqual(gen.error_code, ErrorCode.DOWNLOAD_FAILED)
        # repo 에 영속됐는지(직접 대입 우회 아님)
        self.assertEqual(svc._repo.get(gen.id).status, GenerationStatus.FAILED)

    async def test_success_completes_to_succeeded(self):
        # 결함8 회귀: POST_PROCESSING 도달 후 다운로드 성공 시 worker 가 SUCCEEDED 로 완료.
        svc, worker, gen = await self._submit(None)
        gen.status = GenerationStatus.PROCESSING
        provider = MockVideoProvider(MockScenario.SUCCESS, processing_polls=0)
        gen = await worker.advance_once(gen, provider)
        self.assertEqual(gen.status, GenerationStatus.SUCCEEDED)
        self.assertEqual(gen.output_asset_id, "mock-output-asset")
        self.assertEqual(svc._repo.get(gen.id).status, GenerationStatus.SUCCEEDED)

    async def test_missing_output_url_fails(self):
        # 결함#4 회귀: POST_PROCESSING 에서 결과 URL 부재는 성공이 아니라 다운로드 실패.
        svc, worker, gen = await self._submit(None)
        gen.status = GenerationStatus.POST_PROCESSING

        class _NoUrlProvider(MockVideoProvider):
            async def get_status(self, external_job_id: str):
                from app.domain.enums import ProviderJobStatus
                from app.providers.video_generation.base import VideoStatusResult
                return VideoStatusResult(status=ProviderJobStatus.SUCCEEDED, output_url=None)

        gen = await worker.advance_once(gen, _NoUrlProvider(MockScenario.SUCCESS))
        self.assertEqual(gen.status, GenerationStatus.FAILED)
        self.assertEqual(gen.error_code, ErrorCode.DOWNLOAD_FAILED)

    async def test_fail_generation_noop_on_terminal(self):
        # 이미 SUCCEEDED 인 작업은 FAILED 로 역행하지 않는다(§4.16).
        svc, _worker, gen = await self._submit(None)
        gen.status = GenerationStatus.SUCCEEDED
        svc.fail_generation(gen, GenerationType.VIDEO, ErrorCode.DOWNLOAD_FAILED)
        self.assertEqual(gen.status, GenerationStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
