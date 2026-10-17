"""Supabase JWT 검증부(decode_supabase_jwt) 단위 테스트.

네트워크 없이 자체 EC(ES256) 키쌍으로 토큰을 서명해 검증한다.
PyJWT[crypto](cryptography)가 설치돼 있어야 실행된다 — 없으면 skip.
"""

from __future__ import annotations

import unittest

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import ec

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - 환경에 crypto 없을 때
    _HAS_CRYPTO = False

from app.api.auth import decode_supabase_jwt

_ISS = "https://example.supabase.co/auth/v1"
_AUD = "authenticated"


def _keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


@unittest.skipUnless(_HAS_CRYPTO, "PyJWT[crypto] 미설치 — JWT 검증 테스트 skip")
class TestDecodeSupabaseJwt(unittest.TestCase):
    def test_valid_token_returns_payload(self):
        priv, pub = _keypair()
        token = jwt.encode(
            {"sub": "user-123", "aud": _AUD, "iss": _ISS}, priv, algorithm="ES256"
        )
        payload = decode_supabase_jwt(token, pub, _AUD, _ISS)
        self.assertEqual(payload["sub"], "user-123")

    def test_wrong_audience_rejected(self):
        priv, pub = _keypair()
        token = jwt.encode(
            {"sub": "u", "aud": "other-aud", "iss": _ISS}, priv, algorithm="ES256"
        )
        with self.assertRaises(jwt.InvalidAudienceError):
            decode_supabase_jwt(token, pub, _AUD, _ISS)

    def test_wrong_issuer_rejected(self):
        priv, pub = _keypair()
        token = jwt.encode(
            {"sub": "u", "aud": _AUD, "iss": "https://evil/auth/v1"}, priv, algorithm="ES256"
        )
        with self.assertRaises(jwt.InvalidIssuerError):
            decode_supabase_jwt(token, pub, _AUD, _ISS)

    def test_bad_signature_rejected(self):
        priv_a, _ = _keypair()
        _, pub_b = _keypair()  # 다른 키쌍의 공개키로 검증 → 실패
        token = jwt.encode(
            {"sub": "u", "aud": _AUD, "iss": _ISS}, priv_a, algorithm="ES256"
        )
        with self.assertRaises(jwt.InvalidSignatureError):
            decode_supabase_jwt(token, pub_b, _AUD, _ISS)


if __name__ == "__main__":
    unittest.main()
