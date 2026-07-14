"""Webhook 처리 서비스 — 서명검증·중복안전·상태전이(규칙 §4.15).

순서:
    1. 타임스탬프 허용범위(재전송 완화)
    2. 서명 검증(event_ts 를 payload 와 결합해 서명 — timestamp 위·변조 방지). 실패 시 상태 변경 안 함.
    3. external_job_id 로 작업 조회 — **없으면(순서역전) processed 기록 없이 반환**(재시도 허용)
    4. 이미 처리한 이벤트인지 — 키는 **(provider, event_id)**(provider 간 event_id 충돌 방지)
    5. 상태 전이(can_transition no-op — 역행/중복 무해화)
    6. 후처리 Job 등록은 멱등 key(generation_id:postprocess)로 1회만

무거운 다운로드·FFmpeg 는 여기서 하지 않는다(§4.15) — Worker 로 넘긴다.

⚠️ 스캐폴드 한계(운영 수준 아님): 중복·후처리 등록을 인메모리 set 으로 추적한다. 프로세스 재시작·
멀티 워커·다중 인스턴스에서는 중복 방지가 깨진다 — 실서비스는 DB(처리된 event 테이블/UNIQUE)로
영속해야 한다(로드맵). 서명 포맷도 스캐폴드용 제네릭 HMAC 이며, 실 Provider 서명 규격은 각
Provider 스펙(unverified)을 따른다.
"""

from __future__ import annotations

from app.core.security import is_timestamp_fresh, verify_signature
from app.domain.enums import ErrorCode, GenerationType, ProviderJobStatus
from app.domain.errors import WebhookSignatureInvalid
from app.services.generation_service import GenerationService


def build_signed_message(event_ts: int, payload: bytes) -> bytes:
    """서명 대상 = timestamp + payload(스캐폴드 규격). ts 를 서명에 묶어 재전송·위조를 막는다."""
    return str(event_ts).encode("utf-8") + b"." + payload


class WebhookService:
    def __init__(self, service: GenerationService) -> None:
        self._service = service
        self._processed_event_ids: set[tuple[str, str]] = set()  # (provider, event_id)
        self._postprocess_registered: set[str] = set()

    def _verify(
        self, secret: str, payload: bytes, signature: str, event_ts: int, now_ts: int
    ) -> None:
        if not is_timestamp_fresh(event_ts, now_ts):
            raise WebhookSignatureInvalid("timestamp out of range")
        signed = build_signed_message(event_ts, payload)
        if not verify_signature(secret, signed, signature):
            raise WebhookSignatureInvalid("signature mismatch")

    def handle_status_event(
        self,
        *,
        secret: str,
        payload: bytes,
        signature: str,
        event_ts: int,
        now_ts: int,
        event_id: str,
        provider: str,
        external_job_id: str,
        provider_status: ProviderJobStatus,
        error_code: ErrorCode | None = None,
    ) -> str:
        """검증된 상태 이벤트를 반영하고 결과 상태 문자열을 반환.

        반환값은 반영 후 내부 status(작업 미존재/중복이면 기존 status 또는 "").
        """
        # 2. 서명 검증 (실패 시 상태 변경 없이 예외).
        self._verify(secret, payload, signature, event_ts, now_ts)

        # 3. 작업 조회 — 없으면(순서역전) processed 기록 없이 반환(재시도 허용).
        gen = self._service.get_generation_by_external_job_id(provider, external_job_id)
        if gen is None:
            return ""

        # 4. 중복 이벤트 무시(멱등). provider 별로 event_id 를 구분.
        dedup_key = (provider, event_id)
        if dedup_key in self._processed_event_ids:
            return gen.status.value
        self._processed_event_ids.add(dedup_key)

        # 5. 상태 전이(no-op 안전, FAILED 시 error_code 보존).
        gen = self._service.apply_provider_status(
            gen, provider_status, gen.generation_type, error_code=error_code
        )

        # 6. 후처리 Job 등록(영상 POST_PROCESSING 도달 시 1회만 — 멱등).
        if gen.generation_type is GenerationType.VIDEO and gen.status.value == "POST_PROCESSING":
            key = f"{gen.id}:postprocess"
            if key not in self._postprocess_registered:
                self._postprocess_registered.add(key)
                # 실제 Worker Job 등록은 로드맵. 여기서는 멱등 등록만 보장.
        return gen.status.value
