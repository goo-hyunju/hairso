"""Mock 영상 Provider — 실제 외부 호출 없이 전체 흐름/오류 시나리오를 결정적으로 재현.

규칙 §5.5 Mock Provider 시나리오. 개발/자동 테스트 기본(§0.16).
비용/소요시간은 임의 더미(PLACEHOLDER) — 실 요금 아님.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName
from app.domain.errors import (
    GenerationFailed,
    GenerationPolicyRejected,
    ProviderBalanceExhausted,
    ProviderRateLimited,
)
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoStatusResult,
    VideoSubmissionResult,
)

# PLACEHOLDER — 기획서 §8.3(V6 720p 5초 ≈ 0.20 USD)은 미검증 외부 수치. 실값 아님.
_MOCK_COST_USD = Decimal("0.00")


class MockScenario(str, Enum):
    SUCCESS = "SUCCESS"
    SLOW = "SLOW"  # PROCESSING 여러 번 후 완료
    SUBMIT_FAIL = "SUBMIT_FAIL"
    RATE_LIMIT = "RATE_LIMIT"
    NO_BALANCE = "NO_BALANCE"
    POLICY_BLOCK = "POLICY_BLOCK"
    ASYNC_FAIL = "ASYNC_FAIL"  # 제출 후 처리 중 실패
    DOWNLOAD_FAIL = "DOWNLOAD_FAIL"  # provider 완료지만 결과 URL 다운로드 실패용


class MockVideoProvider(VideoProvider):
    """결정적 Mock. 실제 sleep 없이 poll 카운터로 지연을 흉내낸다."""

    def __init__(
        self,
        scenario: MockScenario = MockScenario.SUCCESS,
        processing_polls: int = 2,
    ) -> None:
        self._scenario = scenario
        self._processing_polls = processing_polls if scenario is not MockScenario.SLOW else 5
        self._polls: dict[str, int] = {}

    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        if self._scenario is MockScenario.RATE_LIMIT:
            raise ProviderRateLimited()
        if self._scenario is MockScenario.NO_BALANCE:
            raise ProviderBalanceExhausted()
        if self._scenario is MockScenario.POLICY_BLOCK:
            raise GenerationPolicyRejected()
        if self._scenario is MockScenario.SUBMIT_FAIL:
            raise GenerationFailed()
        job_id = f"mock-video-{data.idempotency_key}"
        self._polls[job_id] = 0
        return VideoSubmissionResult(
            provider=ProviderName.MOCK,
            external_job_id=job_id,
            ai_trace_id=None,
            estimated_cost_usd=_MOCK_COST_USD,
        )

    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        n = self._polls.get(external_job_id, 0)
        self._polls[external_job_id] = n + 1

        if self._scenario is MockScenario.ASYNC_FAIL:
            return VideoStatusResult(
                status=ProviderJobStatus.FAILED,
                error_code=ErrorCode.GENERATION_FAILED,
            )
        if n < self._processing_polls:
            return VideoStatusResult(status=ProviderJobStatus.PROCESSING)
        if self._scenario is MockScenario.DOWNLOAD_FAIL:
            # provider 는 완료(SUCCEEDED)를 알리지만 Worker 다운로드가 실패할 URL.
            return VideoStatusResult(
                status=ProviderJobStatus.SUCCEEDED,
                output_url="mock://download-fail",
            )
        return VideoStatusResult(
            status=ProviderJobStatus.SUCCEEDED,
            output_url="mock://video.mp4",
        )
