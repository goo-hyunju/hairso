"""도메인 예외 — core.exceptions.AppError 를 상속하고 ErrorCode 를 덧붙인다.

retryable 플래그로 §4.17 재시도/비재시도를 예외에 인코딩한다.
Worker/Service 는 이 플래그만 보고 지수백오프 여부를 결정한다.
"""

from __future__ import annotations

from app.core.exceptions import AppError
from app.domain.enums import ErrorCode


class DomainError(AppError):
    """도메인 규칙 위반의 베이스."""

    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.error_code.value)


class InvalidStateTransition(DomainError):
    """허용되지 않은 상태 전이(내부 버그 검출용). webhook 경로는 예외 대신 no-op 을 쓴다."""

    error_code = ErrorCode.INTERNAL_ERROR
    retryable = False


class ConsentRequired(DomainError):
    error_code = ErrorCode.CONSENT_REQUIRED
    retryable = False


class GenerationDuplicated(DomainError):
    error_code = ErrorCode.GENERATION_DUPLICATED
    retryable = False


class ProviderRateLimited(DomainError):
    error_code = ErrorCode.PROVIDER_RATE_LIMITED
    retryable = True  # 일시적 — 지수백오프 재시도 대상


class ProviderBalanceExhausted(DomainError):
    error_code = ErrorCode.PROVIDER_BALANCE_EXHAUSTED
    retryable = False  # 잔액 부족 — 재시도 무의미


class GenerationPolicyRejected(DomainError):
    error_code = ErrorCode.GENERATION_POLICY_REJECTED
    retryable = False  # 콘텐츠 정책 위반 — 재시도 금지


class GenerationFailed(DomainError):
    error_code = ErrorCode.GENERATION_FAILED
    retryable = False


class DownloadFailed(DomainError):
    error_code = ErrorCode.DOWNLOAD_FAILED
    retryable = True  # 결과 다운로드 일시 실패 — 재시도 대상


class WebhookSignatureInvalid(DomainError):
    error_code = ErrorCode.WEBHOOK_SIGNATURE_INVALID
    retryable = False


class CreditInsufficient(DomainError):
    error_code = ErrorCode.CREDIT_INSUFFICIENT
    retryable = False
