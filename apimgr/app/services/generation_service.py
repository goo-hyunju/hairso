"""생성 작업 서비스 — 제출 흐름 + 외부 상태 반영(순수 로직, stdlib).

흐름(규칙 §4.9/§13):
    1. idempotency 예약(중복이면 기존 작업 반환 — 재제출 안 함)
    2. CREATED 저장 (트랜잭션 경계 종료)
    3. provider.submit (트랜잭션 밖 외부 호출)
    4. 성공 -> SUBMITTED, DomainError -> FAILED(error_code 보존)

영속은 repo.update(gen)(전체 객체) — status 만 저장하면 external_job_id·error_code·cost 가
실 DB 에서 유실된다. 외부 상태 반영은 apply_provider_status(매핑 + can_transition no-op).
실패는 fail_generation, 완료는 complete_generation 으로 일원화(상태머신 가드 + 전체 영속).
"""

from __future__ import annotations

from app.domain import status_mapping
from app.domain.enums import (
    ErrorCode,
    GenerationStatus,
    GenerationType,
    ProviderJobStatus,
    ProviderName,
)
from app.domain.errors import DomainError
from app.domain.models import Generation
from app.domain.state_machine import can_transition, is_terminal
from app.providers.video_generation.base import VideoGenerationInput, VideoProvider
from app.repositories.generation_repository import GenerationRepository


class GenerationService:
    def __init__(self, repo: GenerationRepository) -> None:
        self._repo = repo

    def get_generation(self, generation_id: str) -> Generation | None:
        """id 로 조회 — Router 가 Repository 에 직접 접근하지 않도록 하는 서비스 경계 메서드."""
        return self._repo.get(generation_id)

    def get_generation_by_external_job_id(
        self, provider: str, external_job_id: str
    ) -> Generation | None:
        """webhook/worker 용 조회 — Repository private 접근을 피하는 서비스 경계 메서드."""
        return self._repo.get_by_external_job_id(provider, external_job_id)

    async def create_video_generation(
        self,
        generation_id: str,
        consultation_id: str,
        input_data: VideoGenerationInput,
        provider: VideoProvider,
    ) -> Generation:
        # 1. Idempotency — 동일 key 재요청은 기존 작업을 반환하고 재제출하지 않는다.
        #    스캐폴드는 조회 후 저장(check-then-save). 실서비스의 동시성 방어는
        #    DB `idempotency_key` UNIQUE 제약이 담당한다(§4.10, 로드맵) — 코드 선조회만으로
        #    막았다고 판단하지 않는다.
        existing = self._repo.get_by_idempotency_key(input_data.idempotency_key)
        if existing is not None:
            return existing

        # 2. CREATED 저장 (트랜잭션 경계 — 외부 호출 전에 종료).
        gen = Generation(
            id=generation_id,
            consultation_id=consultation_id,
            generation_type=GenerationType.VIDEO,
            provider=ProviderName.MOCK,  # submit 결과로 실제 provider 반영
            status=GenerationStatus.CREATED,
            idempotency_key=input_data.idempotency_key,
            input_asset_id=input_data.image_asset_id,
            prompt=input_data.prompt,
            negative_prompt=input_data.negative_prompt,
        )
        self._repo.save(gen)

        # 3. 외부 제출 (트랜잭션 밖). 4. 결과 반영.
        try:
            result = await provider.submit(input_data)
        except DomainError as exc:
            self.fail_generation(gen, GenerationType.VIDEO, exc.error_code, str(exc))
            return gen

        gen.provider = result.provider
        gen.external_job_id = result.external_job_id
        gen.ai_trace_id = result.ai_trace_id
        gen.estimated_cost_usd = result.estimated_cost_usd
        gen.status = GenerationStatus.SUBMITTED
        self._repo.update(gen)  # 전체 영속(external_job_id·cost 포함)
        return gen

    def apply_provider_status(
        self,
        gen: Generation,
        provider_status: ProviderJobStatus,
        gen_type: GenerationType,
        error_code: ErrorCode | None = None,
    ) -> Generation:
        """외부 provider 상태를 내부 상태로 반영. 역행/동일상태는 no-op(멱등).

        FAILED 로 전이할 때 provider 가 준 error_code 를 보존한다(§4.7).
        """
        candidate = status_mapping.map_provider_status(gen_type, provider_status)
        # 동일 상태거나 불법(역행/터미널 이후) 전이면 무시 — webhook 중복/순서역전 안전(§4.15/§4.16).
        if candidate == gen.status:
            return gen
        if not can_transition(gen_type, gen.status, candidate):
            return gen
        gen.status = candidate
        if candidate is GenerationStatus.FAILED and error_code is not None:
            gen.error_code = error_code
        self._repo.update(gen)
        return gen

    def fail_generation(
        self,
        gen: Generation,
        gen_type: GenerationType,
        error_code: ErrorCode,
        message: str = "",
    ) -> Generation:
        """작업을 FAILED 로 전이(상태머신 가드 + 전체 영속 + error_code 저장).

        이미 터미널(FAILED/CANCELED/EXPIRED)이면 no-op — 기존 실패 원인을 덮어쓰지 않는다.
        """
        if is_terminal(gen.status):
            return gen
        if not can_transition(gen_type, gen.status, GenerationStatus.FAILED):
            return gen
        gen.status = GenerationStatus.FAILED
        gen.error_code = error_code
        gen.error_message = message
        self._repo.update(gen)
        return gen

    def complete_generation(
        self,
        gen: Generation,
        gen_type: GenerationType,
        output_asset_id: str | None = None,
    ) -> Generation:
        """후처리 완료 시 SUCCEEDED 로 전이(§13 'worker 완료 시 SUCCEEDED'). 불법이면 no-op."""
        if not can_transition(gen_type, gen.status, GenerationStatus.SUCCEEDED):
            return gen
        gen.status = GenerationStatus.SUCCEEDED
        if output_asset_id is not None:
            gen.output_asset_id = output_asset_id
        self._repo.update(gen)
        return gen
