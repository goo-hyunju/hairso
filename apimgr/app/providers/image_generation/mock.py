"""Mock 이미지 생성 Provider — 결정적. IMAGE 는 후처리 없음(provider SUCCEEDED -> 내부 SUCCEEDED).

store 가 주입되면 결과 바이트(_MOCK_PNG)를 실제 저장소에 기록해, 실 provider 와 동일한
'결과 에셋 등록' 경로(register_generated_image)를 그대로 태운다. 저장 경로는 실 provider
(generated/{id}.png)와 분리(generated/mock/{id}.png)해 mock 산출물이 섞이지 않게 한다.
store 미주입 시(순수 단위 테스트)에는 저장을 건너뛰고 상태만 결정적으로 보고한다.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName
from app.domain.errors import GenerationPolicyRejected, ProviderRateLimited
from app.providers.image_generation.base import (
    ImageGenerationInput,
    ImageProvider,
    ImageStatusResult,
    ImageSubmissionResult,
)
from app.providers.storage.base import AssetStore
from app.providers.video_generation.mock import MockScenario  # 시나리오 열거 재사용

_MOCK_COST_USD = Decimal("0.00")  # PLACEHOLDER — 미검증
# 1x1 투명 PNG(유효 시그니처 \x89PNG…). 실제 추론 대신 결정적 더미 결과 바이트.
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
        store: AssetStore | None = None,
    ) -> None:
        self._scenario = scenario
        self._processing_polls = processing_polls
        self._store = store
        self._polls: dict[str, int] = {}

    @staticmethod
    def output_key(external_job_id: str) -> str:
        """mock 결과 저장 키 — 실 provider(generated/{id}.png)와 분리된 전용 경로."""
        return f"generated/mock/{external_job_id}.png"

    async def submit(self, data: ImageGenerationInput) -> ImageSubmissionResult:
        if self._scenario is MockScenario.RATE_LIMIT:
            raise ProviderRateLimited()
        if self._scenario is MockScenario.POLICY_BLOCK:
            raise GenerationPolicyRejected()
        job_id = f"mock-image-{data.idempotency_key}-{data.variant.value}"
        self._polls[job_id] = 0
        # 결과 바이트를 실제 저장소에 기록 — 실 provider 와 동일한 등록 경로를 태운다.
        if self._store is not None:
            self._store.save(self.output_key(job_id), _MOCK_PNG, "image/png")
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
        # SUCCEEDED 의 output_url 은 submit 이 저장한 실제 키(register 가 이 키로 바이트 로드).
        return ImageStatusResult(
            status=ProviderJobStatus.SUCCEEDED, output_url=self.output_key(external_job_id)
        )
