"""도메인 enum — FE(Zod)와 문자열 리터럴이 정확히 일치해야 하는 계약의 단일 출처.

`str, Enum` 상속: JSON 직렬화 시 값이 그대로 문자열이 되어 FE Zod enum 과 일치시키기 쉽다.
값 변경 시 contract/enums.json 및 FE 스키마와 동기화(F8 parity 테스트가 강제).
"""

from __future__ import annotations

from enum import Enum


class GenerationStatus(str, Enum):
    """생성 작업 내부 상태(10개). FE GenerationStatus 와 동일 리터럴."""

    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    POST_PROCESSING = "POST_PROCESSING"  # FFmpeg 후처리 — 영상 전용
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class GenerationType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class ProviderName(str, Enum):
    """AI Provider 레지스트리(7개). 규칙 §4.8: WAN_CLOUD_API 채택(기획서 ALIBABA_WAN 은 별칭).

    GEMINI 는 image_analysis/image_generation 소속 — 영상 provider 가 아니다(FE VideoProviderName 에서 제외).
    """

    MOCK = "MOCK"
    GEMINI = "GEMINI"
    PIXVERSE = "PIXVERSE"
    FAL_WAN = "FAL_WAN"
    WAN_CLOUD_API = "WAN_CLOUD_API"  # 기획서 §12 별칭: ALIBABA_WAN
    SELF_HOSTED_WAN = "SELF_HOSTED_WAN"
    LOCAL_SD = "LOCAL_SD"  # 로컬 자체호스팅 SD inpainting(이미지 전용) — §4.8 self-hosted


class ProviderJobStatus(str, Enum):
    """외부 Provider 가 보고하는 작업 상태(4개) — 내부 GenerationStatus(10개)와 다른 레이어.

    Service 가 status_mapping 으로 내부 상태 후보로 변환한 뒤 state_machine 이 최종 판정한다.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ErrorCode(str, Enum):
    """내부 오류코드(18개). FE ApiErrorCode 와 동일 리터럴(§5.3 + 보강)."""

    # §5.3 기본
    ASSET_INVALID = "ASSET_INVALID"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    GENERATION_DUPLICATED = "GENERATION_DUPLICATED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_BALANCE_EXHAUSTED = "PROVIDER_BALANCE_EXHAUSTED"
    GENERATION_POLICY_REJECTED = "GENERATION_POLICY_REJECTED"
    GENERATION_FAILED = "GENERATION_FAILED"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    # 보강
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CREDIT_INSUFFICIENT = "CREDIT_INSUFFICIENT"
    SHARE_EXPIRED = "SHARE_EXPIRED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


class StudioTemplateType(str, Enum):
    """Studio 공개 템플릿 타입. 제품 중심은 범용 쇼츠이고 Hair 는 카테고리 중 하나다."""

    HAIR_STYLING_MOTION = "HAIR_STYLING_MOTION"
    PROMOTION_SHORT = "PROMOTION_SHORT"
    SALON_EVENT_PROMOTION = "SALON_EVENT_PROMOTION"
    FREE_IMAGE_TO_VIDEO = "FREE_IMAGE_TO_VIDEO"


class StudioCategory(str, Enum):
    """Studio 콘텐츠 카테고리. Hair 는 기본 카테고리일 뿐 제품 전체 중심은 아니다."""

    HAIR = "HAIR"
    BEAUTY = "BEAUTY"
    HEALTH = "HEALTH"
    PRODUCT = "PRODUCT"
    LOCAL_BUSINESS = "LOCAL_BUSINESS"
    PET = "PET"
    GENERAL = "GENERAL"


class StudioTone(str, Enum):
    """Studio 초안 문구 톤. FE 선택값과 동일 리터럴."""

    CALM = "CALM"
    TRENDY = "TRENDY"
    PREMIUM = "PREMIUM"
    FRIENDLY = "FRIENDLY"


class StudioProjectStatus(str, Enum):
    """Studio 프로젝트 상태. 생성 job 상태와 분리된 제품 레이어 상태."""

    DRAFTING = "DRAFTING"
    DRAFT_READY = "DRAFT_READY"
    RENDERING = "RENDERING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CreditTxType(str, Enum):
    """크레딧 원장 트랜잭션 유형(§4.12 5분류 매핑)."""

    RESERVE = "RESERVE"
    CHARGE = "CHARGE"
    REFUND = "REFUND"
    ADJUST = "ADJUST"
