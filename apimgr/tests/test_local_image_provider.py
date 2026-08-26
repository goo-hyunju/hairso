"""LOCAL_SD provider 보안 경계 테스트."""

import unittest

from app.domain.errors import GenerationFailed
from app.providers.image_generation.local import LocalImageProvider
from app.providers.storage.base import AssetStore


class _Store(AssetStore):
    def save(self, key: str, data: bytes, content_type: str) -> None:
        return None

    def load(self, key: str) -> bytes:
        raise FileNotFoundError(key)

    def exists(self, key: str) -> bool:
        return False


class TestLocalImageProvider(unittest.TestCase):
    def test_rejects_non_local_base_url(self):
        with self.assertRaises(GenerationFailed):
            LocalImageProvider(_Store(), "https://example.com")

    def test_accepts_loopback_base_url(self):
        provider = LocalImageProvider(_Store(), "http://127.0.0.1:8188")

        self.assertEqual(provider.face_key("asset-1"), "face/asset-1.png")


if __name__ == "__main__":
    unittest.main()
