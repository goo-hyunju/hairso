"""domain 모델 dataclass 스모크 — 필드명이 DDL 컬럼과 정합(F8)한지 최소 검증."""
import unittest
from datetime import datetime

from app.domain.models import Asset, Consent


class TestDomainModels(unittest.TestCase):
    def test_asset_minimal_construct(self):
        a = Asset(
            id="a1",
            owner_type="SALON_MEMBER",
            asset_type="FACE_SOURCE",
            storage_key="face/a1",
            mime_type="image/jpeg",
            byte_size=12345,
        )
        self.assertEqual(a.asset_type, "FACE_SOURCE")
        self.assertIsInstance(a.created_at, datetime)
        self.assertIsNone(a.expires_at)

    def test_consent_minimal_construct(self):
        c = Consent(
            id="c1",
            consent_type="EXTERNAL_AI_TRANSFER",
            granted=True,
            policy_version="v1",
        )
        self.assertTrue(c.granted)
        self.assertEqual(c.consent_type, "EXTERNAL_AI_TRANSFER")


if __name__ == "__main__":
    unittest.main()
