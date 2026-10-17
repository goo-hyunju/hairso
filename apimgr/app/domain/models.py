"""도메인 모델 — dataclass(순수 stdlib). API 스키마(pydantic)와 분리한다(규칙 §4.5).

비용 필드는 전부 Decimal(돈 = float 반올림 오차 방지, 규칙 §11-2 데이터 무결성).
필드명은 DDL 컬럼명·snake_case 와 일치(F8 게이트).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.enums import (
    CreditTxType,
    ErrorCode,
    GenerationStatus,
    GenerationType,
    ProviderName,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Generation:
    """생성 작업(이미지/영상). generations 테이블 대응."""

    id: str
    consultation_id: str
    generation_type: GenerationType
    provider: ProviderName
    status: GenerationStatus
    idempotency_key: str
    created_by: str | None = None  # auth.users(id) — 인증된 요청자(선택적 인증, 익명이면 None)
    model: str | None = None
    batch_id: str | None = None  # 이미지 3종 묶음(영상은 None)
    external_job_id: str | None = None
    ai_trace_id: str | None = None  # PixVerse Ai-trace-id (외부, 내부 key 와 별도)
    input_asset_id: str | None = None
    output_asset_id: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    estimated_cost_usd: Decimal | None = None
    actual_cost_usd: Decimal | None = None
    error_code: ErrorCode | None = None
    error_message: str | None = None
    share_token: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    submitted_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class CreditTransaction:
    """크레딧 원장 1행. credit_transactions 테이블 대응."""

    id: str
    salon_id: str | None
    tx_type: CreditTxType
    amount_credit: Decimal
    generation_id: str | None = None
    balance_after: Decimal | None = None
    estimated_cost_usd: Decimal | None = None
    actual_cost_usd: Decimal | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Asset:
    """파일 메타데이터. assets 테이블 대응(원본·공개 URL 미저장, §4.13)."""

    id: str
    owner_type: str  # SALON_MEMBER / CUSTOMER / SYSTEM
    asset_type: str  # FACE_SOURCE / GENERATED_VIDEO 등
    storage_key: str
    mime_type: str
    byte_size: int
    owner_id: str | None = None  # auth.users(id)
    consultation_id: str | None = None  # MVP nullable
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    status: str = "ACTIVE"
    expires_at: datetime | None = None  # FACE_SOURCE=+24h / GENERATED_VIDEO=+7d
    deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Consent:
    """동의 1건. consents 테이블 대응. 없으면 CONSENT_REQUIRED(§3.9)."""

    id: str
    consent_type: str  # FACE_PROCESSING / EXTERNAL_AI_TRANSFER / STORAGE / RESULT_SHARE
    granted: bool
    policy_version: str
    account_id: str | None = None  # auth.users(id)
    consultation_id: str | None = None  # MVP nullable
    customer_id: str | None = None  # MVP nullable
    ip_hash: str | None = None
    user_agent: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime = field(default_factory=_utcnow)
