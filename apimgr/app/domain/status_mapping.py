"""외부 ProviderJobStatus(4) -> 내부 GenerationStatus(10) 후보 매핑.

순수 dict + 함수(stdlib) — 오프라인 unittest 로 검증 가능.

핵심(D7): provider 가 SUCCEEDED 를 줘도 곧바로 내부 SUCCEEDED 로 가지 않는다.
    - VIDEO : provider SUCCEEDED -> 내부 POST_PROCESSING (다운로드·R2·FFmpeg 후처리 대기).
              내부 SUCCEEDED 는 후처리 Worker 완료가 트리거.
    - IMAGE : 후처리가 없으므로 provider SUCCEEDED -> 내부 SUCCEEDED 직행.

이 매핑은 '목표 후보'만 산출한다. 실제 채택/무시는 state_machine.can_transition 이 최종 판정한다
(동일 상태 재폴링·역행 이벤트는 no-op).
"""

from __future__ import annotations

from app.domain.enums import GenerationStatus as S
from app.domain.enums import GenerationType, ProviderJobStatus

_VIDEO_MAP: dict[ProviderJobStatus, S] = {
    ProviderJobStatus.PENDING: S.QUEUED,
    ProviderJobStatus.PROCESSING: S.PROCESSING,
    ProviderJobStatus.SUCCEEDED: S.POST_PROCESSING,  # 후처리 대기
    ProviderJobStatus.FAILED: S.FAILED,
}

_IMAGE_MAP: dict[ProviderJobStatus, S] = {
    ProviderJobStatus.PENDING: S.QUEUED,
    ProviderJobStatus.PROCESSING: S.PROCESSING,
    ProviderJobStatus.SUCCEEDED: S.SUCCEEDED,  # 후처리 없음 — 직행
    ProviderJobStatus.FAILED: S.FAILED,
}

_MAPS: dict[GenerationType, dict[ProviderJobStatus, S]] = {
    GenerationType.IMAGE: _IMAGE_MAP,
    GenerationType.VIDEO: _VIDEO_MAP,
}


def map_provider_status(gen_type: GenerationType, provider_status: ProviderJobStatus) -> S:
    """외부 provider 상태를 내부 상태 후보로 변환한다."""
    return _MAPS[gen_type][provider_status]
