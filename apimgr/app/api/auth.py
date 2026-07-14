"""Supabase JWT(JWKS ES256) 검증 — 선택적 인증의 검증부.

이 프로젝트 Supabase 는 비대칭 서명키(ES256)를 사용한다. BE 는 JWT secret 없이
공개키(JWKS)로 토큰을 검증한다 — 더 안전하고 키 회전이 독립적이다.

계층: 순수 계층 아님(jwt·네트워크). deps 가 이용한다.
- `decode_supabase_jwt`: 서명키·audience·issuer 로 검증(네트워크 없음 — 단위 테스트 대상).
- `SupabaseJWTVerifier`: JWKS 엔드포인트에서 서명키를 받아 검증(런타임, PyJWKClient 내부 캐시).
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient


def decode_supabase_jwt(
    token: str,
    signing_key: Any,
    audience: str,
    issuer: str,
    algorithms: tuple[str, ...] = ("ES256",),
) -> dict[str, Any]:
    """토큰을 서명키로 검증하고 payload(dict)를 반환한다.

    서명 불일치·aud/iss 불일치·만료는 각각 jwt 예외를 던진다(호출측이 401 처리).
    """
    return jwt.decode(
        token,
        signing_key,
        algorithms=list(algorithms),
        audience=audience,
        issuer=issuer,
    )


class SupabaseJWTVerifier:
    """Supabase URL 로부터 JWKS·issuer 를 구성해 토큰을 검증한다."""

    def __init__(self, supabase_url: str, audience: str) -> None:
        base = supabase_url.rstrip("/")
        self._jwks_client = PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json")
        self._audience = audience
        self._issuer = f"{base}/auth/v1"

    def verify(self, token: str) -> dict[str, Any]:
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return decode_supabase_jwt(token, signing_key.key, self._audience, self._issuer)
