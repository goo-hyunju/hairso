"""Mock 이미지 생성 Provider — 결정적. IMAGE 는 후처리 없음(provider SUCCEEDED -> 내부 SUCCEEDED)."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName
from app.domain.errors import GenerationPolicyRejected, ProviderRateLimited
from app.providers.storage.base import AssetStore
from app.providers.image_generation.base import (
    ImageGenerationInput,
    ImageProvider,
    ImageStatusResult,
    ImageSubmissionResult,
)
from app.providers.video_generation.mock import MockScenario  # 시나리오 열거 재사용

_MOCK_COST_USD = Decimal("0.00")  # PLACEHOLDER — 미검증
_MOCK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MockImageProvider(ImageProvider):
    def __init__(
        self,
        scenario: MockScenario = MockScenario.SUCCESS,
        processing_polls: int = 1,
    ) -> None:
        self._scenario = scenario
        self._processing_polls = processing_polls
        self._polls: dict[str, int] = {}

    async def submit(self, data: ImageGenerationInput) -> ImageSubmissionResult:
        if self._scenario is MockScenario.RATE_LIMIT:
            raise ProviderRateLimited()
        if self._scenario is MockScenario.POLICY_BLOCK:
            raise GenerationPolicyRejected()
        job_id = f"mock-image-{data.idempotency_key}-{data.variant.value}"
        self._polls[job_id] = 0
        return ImageSubmissionResult(
            provider=ProviderName.MOCK,
            external_job_id=job_id,
            estimated_cost_usd=_MOCK_COST_USD,
        )

    async def get_status(self, external_job_id: str) -> ImageStatusResult:
        n = self._polls.get(external_job_id, 0)
        self._polls[external_job_id] = n + 1
        if self._scenario is MockScenario.ASYNC_FAIL:
            return ImageStatusResult(
                status=ProviderJobStatus.FAILED, error_code=ErrorCode.GENERATION_FAILED
            )
        if n < self._processing_polls:
            return ImageStatusResult(status=ProviderJobStatus.PROCESSING)
        return ImageStatusResult(
            status=ProviderJobStatus.SUCCEEDED, output_url="mock://image.png"
        )

