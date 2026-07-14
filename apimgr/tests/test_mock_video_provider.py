"""Mock 영상 Provider 8시나리오 테스트 — IsolatedAsyncioTestCase(오프라인)."""

import unittest

from app.domain.enums import ProviderJobStatus
from app.domain.errors import (
    GenerationFailed,
    GenerationPolicyRejected,
    ProviderBalanceExhausted,
    ProviderRateLimited,
)
from app.providers.video_generation.base import VideoGenerationInput
from app.providers.video_generation.mock import MockScenario, MockVideoProvider


def _input(key: str = "idem-1") -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="asset-1",
        prompt="turn head",
        duration_seconds=5,
        aspect_ratio="9:16",
        quality="720p",
        idempotency_key=key,
    )


class TestMockVideoProvider(unittest.IsolatedAsyncioTestCase):
    async def test_success_flow(self):
        p = MockVideoProvider(MockScenario.SUCCESS, processing_polls=2)
        sub = await p.submit(_input())
        self.assertTrue(sub.external_job_id)
        s1 = await p.get_status(sub.external_job_id)
        self.assertEqual(s1.status, ProviderJobStatus.PROCESSING)
        await p.get_status(sub.external_job_id)  # 2nd processing poll
        s3 = await p.get_status(sub.external_job_id)
        self.assertEqual(s3.status, ProviderJobStatus.SUCCEEDED)
        self.assertEqual(s3.output_url, "mock://video.mp4")

    async def test_submit_fail(self):
        with self.assertRaises(GenerationFailed):
            await MockVideoProvider(MockScenario.SUBMIT_FAIL).submit(_input())

    async def test_rate_limit(self):
        with self.assertRaises(ProviderRateLimited):
            await MockVideoProvider(MockScenario.RATE_LIMIT).submit(_input())

    async def test_no_balance(self):
        with self.assertRaises(ProviderBalanceExhausted):
            await MockVideoProvider(MockScenario.NO_BALANCE).submit(_input())

    async def test_policy_block(self):
        with self.assertRaises(GenerationPolicyRejected):
            await MockVideoProvider(MockScenario.POLICY_BLOCK).submit(_input())

    async def test_async_fail(self):
        p = MockVideoProvider(MockScenario.ASYNC_FAIL)
        sub = await p.submit(_input())
        st = await p.get_status(sub.external_job_id)
        self.assertEqual(st.status, ProviderJobStatus.FAILED)

    async def test_download_fail_url(self):
        p = MockVideoProvider(MockScenario.DOWNLOAD_FAIL, processing_polls=0)
        sub = await p.submit(_input())
        st = await p.get_status(sub.external_job_id)
        self.assertEqual(st.status, ProviderJobStatus.SUCCEEDED)
        self.assertEqual(st.output_url, "mock://download-fail")

    async def test_slow_takes_more_polls(self):
        p = MockVideoProvider(MockScenario.SLOW)  # processing_polls forced to 5
        sub = await p.submit(_input())
        for _ in range(5):
            st = await p.get_status(sub.external_job_id)
            self.assertEqual(st.status, ProviderJobStatus.PROCESSING)
        st = await p.get_status(sub.external_job_id)
        self.assertEqual(st.status, ProviderJobStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
