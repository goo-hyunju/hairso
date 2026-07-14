"""서명 검증 등 제네릭 보안 유틸 (stdlib 만 사용, 도메인 무지식)."""

from __future__ import annotations

import hashlib
import hmac


def compute_hmac_sha256(secret: str, payload: bytes) -> str:
    """HMAC-SHA256 16진 문자열을 계산한다."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: bytes, signature: str) -> bool:
    """Webhook 서명 검증.

    타이밍 공격을 피하려고 hmac.compare_digest 로 상수시간 비교한다.
    검증 실패(서명 불일치)면 False — 호출측은 WEBHOOK_SIGNATURE_INVALID 로 처리한다.
    """
    expected = compute_hmac_sha256(secret, payload)
    return hmac.compare_digest(expected, signature)


def is_timestamp_fresh(event_ts: int, now_ts: int, max_skew_seconds: int = 300) -> bool:
    """Webhook 타임스탬프가 허용 오차(기본 5분) 안인지 확인한다(재전송 공격 완화)."""
    return abs(now_ts - event_ts) <= max_skew_seconds
