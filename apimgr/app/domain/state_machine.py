"""생성 작업 상태 전이 규칙 — 단일 출처(규칙 §4.16 "상태전이 한곳 관리").

generation_type 별 전이표를 둔다:
    - IMAGE : 후처리(FFmpeg)가 없으므로 POST_PROCESSING 을 거치지 않는다.
    - VIDEO : PROCESSING -> POST_PROCESSING -> SUCCEEDED.

두 함수:
    - assert_transition : 불법 전이면 예외(내부 결정적 전이의 버그 검출용).
    - can_transition    : 불법 전이면 False(외부 구동 폴링/webhook 의 멱등 no-op 판정용).

핵심: 이미 SUCCEEDED 인 작업에 늦게 도착한 PROCESSING webhook 은
can_transition(SUCCEEDED, PROCESSING) == False → 호출측이 무시(no-op)한다.
"""

from __future__ import annotations

from app.domain.enums import GenerationStatus as S
from app.domain.enums import GenerationType
from app.domain.errors import InvalidStateTransition

_TERMINAL = frozenset({S.FAILED, S.CANCELED, S.EXPIRED})

# 공통 전방 뼈대(타입 무관 부분). SUBMITTED/QUEUED 는 타입별로 확장한다.
_COMMON: dict[S, frozenset[S]] = {
    S.CREATED: frozenset({S.UPLOADING, S.SUBMITTED, S.QUEUED, S.FAILED, S.CANCELED}),
    S.UPLOADING: frozenset({S.SUBMITTED, S.FAILED, S.CANCELED}),
    S.SUCCEEDED: frozenset({S.EXPIRED}),
    S.FAILED: frozenset(),
    S.CANCELED: frozenset(),
    S.EXPIRED: frozenset(),
}

# IMAGE: PROCESSING -> SUCCEEDED 직행(POST_PROCESSING 없음).
# provider 가 중간 상태(PROCESSING)를 건너뛰고 완료를 알릴 수 있으므로 SUBMITTED/QUEUED 에서
# SUCCEEDED 로의 전방 스킵을 허용한다(그렇지 않으면 작업이 영구 정체된다).
_IMAGE: dict[S, frozenset[S]] = {
    **_COMMON,
    S.SUBMITTED: frozenset({S.QUEUED, S.PROCESSING, S.SUCCEEDED, S.FAILED, S.CANCELED}),
    S.QUEUED: frozenset({S.PROCESSING, S.SUCCEEDED, S.FAILED, S.CANCELED}),
    S.PROCESSING: frozenset({S.SUCCEEDED, S.FAILED, S.CANCELED}),
    S.POST_PROCESSING: frozenset(),  # IMAGE 에는 도달하지 않는 상태
}

# VIDEO: PROCESSING -> POST_PROCESSING -> SUCCEEDED.
# provider 가 PROCESSING 을 건너뛰고 완료(→POST_PROCESSING 매핑)를 알릴 수 있으므로
# SUBMITTED/QUEUED 에서 POST_PROCESSING 으로의 전방 스킵을 허용한다.
_VIDEO: dict[S, frozenset[S]] = {
    **_COMMON,
    S.SUBMITTED: frozenset({S.QUEUED, S.PROCESSING, S.POST_PROCESSING, S.FAILED, S.CANCELED}),
    S.QUEUED: frozenset({S.PROCESSING, S.POST_PROCESSING, S.FAILED, S.CANCELED}),
    S.PROCESSING: frozenset({S.POST_PROCESSING, S.FAILED, S.CANCELED}),
    S.POST_PROCESSING: frozenset({S.SUCCEEDED, S.FAILED}),
}

_TABLES: dict[GenerationType, dict[S, frozenset[S]]] = {
    GenerationType.IMAGE: _IMAGE,
    GenerationType.VIDEO: _VIDEO,
}


def is_terminal(status: S) -> bool:
    """전이 그래프상 종료 상태(outgoing 전이 없음)인지.

    ⚠️ SUCCEEDED 는 여기서 False 다 — SUCCEEDED -> EXPIRED 전이가 있기 때문(결과 만료).
    이는 FE `generationStatusView.SUCCEEDED.isTerminal = true`("UI 최종, 더 진행 없음")와
    의미가 다르다: BE=전이-종료(FAILED/CANCELED/EXPIRED), FE=UI-최종(SUCCEEDED 포함). 혼동 금지.
    """
    return status in _TERMINAL


def can_transition(gen_type: GenerationType, current: S, target: S) -> bool:
    """current -> target 이 gen_type 규칙상 허용되는지(불법이면 False, 예외 없음)."""
    return target in _TABLES[gen_type].get(current, frozenset())


def assert_transition(gen_type: GenerationType, current: S, target: S) -> None:
    """불법 전이면 InvalidStateTransition 을 던진다(내부 결정적 전이용)."""
    if not can_transition(gen_type, current, target):
        raise InvalidStateTransition(
            f"{gen_type.value}: {current.value} -> {target.value} not allowed"
        )
