"""API 계층 테스트 — 오류 envelope·요청 검증 (deps 계층, FastAPI TestClient)."""

import os
import unittest

# 데모 Mock 전진 간격을 0으로 두어 background task 가 테스트를 지연시키지 않게 한다.
os.environ.setdefault("MOCK_ADVANCE_INTERVAL_SEC", "0")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


class TestApiEnvelope(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(main.app)

    def test_404_uses_error_envelope(self):
        # 결함#3 회귀: 404 가 { error: { error_code, message, request_id } } 형식이어야 한다.
        r = self.c.get("/api/v1/generations/does-not-exist")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["error_code"], "NOT_FOUND")
        self.assertIn("request_id", body["error"])

    def test_validation_error_uses_envelope(self):
        # 결함#6 회귀: 빈 prompt 는 422 + VALIDATION_ERROR envelope.
        r = self.c.post(
            "/api/v1/video-generations",
            json={"consultation_id": "c1", "image_asset_id": "a1", "prompt": "", "idempotency_key": "k"},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")

    def test_video_generation_accepts_and_returns_202(self):
        r = self.c.post(
            "/api/v1/video-generations",
            json={"consultation_id": "c1", "image_asset_id": "a1", "prompt": "turn head", "idempotency_key": "api-k1"},
        )
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["status"], "SUBMITTED")

    def test_estimated_cost_is_number(self):
        # 결함#12 회귀: 금전 와이어값은 number(float), string 아님.
        r = self.c.post(
            "/api/v1/video-generations",
            json={"consultation_id": "c1", "image_asset_id": "a1", "prompt": "x", "idempotency_key": "api-k2"},
        )
        gid = r.json()["generation_id"]
        cost = self.c.get(f"/api/v1/generations/{gid}").json()["estimated_cost_usd"]
        self.assertIsInstance(cost, (int, float))


if __name__ == "__main__":
    unittest.main()
