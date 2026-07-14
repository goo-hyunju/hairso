"""도메인 모델 — dataclass(순수 stdlib). API 스키마(pydantic)와 분리한다(규칙 §4.5).

비용 필드는 전부 Decimal(돈 = float 반올림 오차 방지, 규칙 §11-2 데이터 무결성).
필드명은 DDL 컬럼명·snake_case 와 일치(F8 게이트).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.enums import (
    CreditTxType,
    ErrorCode,
    GenerationStatus,
    GenerationType,
    ProviderName,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Generation:
    """생성 작업(이미지/영상). generations 테이블 대응."""

    id: str
    consultation_id: str
    generation_type: GenerationType
    provider: ProviderName
    status: GenerationStatus
    idempotency_key: str
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
