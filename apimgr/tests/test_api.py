"""API 계층 테스트 — 오류 envelope·요청 검증 (deps 계층, FastAPI TestClient)."""

import os
import unittest

# 데모 Mock 전진 간격을 0으로 두어 background task 가 테스트를 지연시키지 않게 한다.
os.environ.setdefault("MOCK_ADVANCE_INTERVAL_SEC", "0")

from fastapi.testclient import TestClient

import main
from app.api.v1.generations import create_image_generation, create_video_generation
from app.core.security import compute_hmac_sha256
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.schemas.generation import ImageGenerationRequest, VideoGenerationRequest
from app.services.generation_service import GenerationService
from app.services.webhook_service import build_signed_message

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _FakeBackground:
    def __init__(self) -> None:
        self.tasks = []

    def add_task(self, func, *args, **kwargs) -> None:
        self.tasks.append((func, args, kwargs))


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

    def test_idempotency_key_rejects_path_characters(self):
        r = self.c.post(
            "/api/v1/video-generations",
            json={
                "consultation_id": "c1",
                "image_asset_id": "a1",
                "prompt": "x",
                "idempotency_key": "../bad",
            },
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"]["error_code"], "VALIDATION_ERROR")

    def test_asset_content_requires_owner(self):
        uploaded = self.c.post(
            "/api/v1/assets",
            files={"file": ("face.png", _PNG, "image/png")},
        )
        self.assertEqual(uploaded.status_code, 201)
        asset_id = uploaded.json()["asset_id"]

        r = self.c.get(f"/api/v1/assets/{asset_id}/content")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"]["error_code"], "FORBIDDEN")

    def test_webhook_secret_missing_fails_closed(self):
        old_secret = os.environ.pop("PIXVERSE_WEBHOOK_SECRET", None)
        try:
            r = self.c.post("/api/v1/webhooks/pixverse", headers={"x-timestamp": "1"})
        finally:
            if old_secret is not None:
                os.environ["PIXVERSE_WEBHOOK_SECRET"] = old_secret
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["error"]["error_code"], "INTERNAL_ERROR")

    def test_webhook_stale_timestamp_rejected_at_router(self):
        old_secret = os.environ.get("PIXVERSE_WEBHOOK_SECRET")
        os.environ["PIXVERSE_WEBHOOK_SECRET"] = "test-secret"
        payload = b'{"job":"x"}'
        event_ts = 1
        signature = compute_hmac_sha256(
            "test-secret", build_signed_message(event_ts, payload)
        )
        try:
            r = self.c.post(
                "/api/v1/webhooks/pixverse?job_id=missing",
                content=payload,
                headers={
                    "x-timestamp": str(event_ts),
                    "x-signature": signature,
                    "x-event-id": "stale",
                },
            )
        finally:
            if old_secret is None:
                os.environ.pop("PIXVERSE_WEBHOOK_SECRET", None)
            else:
                os.environ["PIXVERSE_WEBHOOK_SECRET"] = old_secret
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["error_code"], "WEBHOOK_SIGNATURE_INVALID")


class TestGenerationRoutes(unittest.IsolatedAsyncioTestCase):
    async def test_video_idempotent_retry_does_not_register_second_background_task(self):
        service = GenerationService(InMemoryGenerationRepository())
        background = _FakeBackground()
        request = VideoGenerationRequest(
            consultation_id="c1",
            image_asset_id="a1",
            prompt="turn head",
            idempotency_key="route-dup-video",
        )

        first = await create_video_generation(request, background, service, object(), None)
        second = await create_video_generation(request, background, service, object(), None)

        self.assertEqual(first.generation_id, second.generation_id)
        self.assertEqual(len(background.tasks), 1)

    async def test_image_idempotent_retry_does_not_register_second_background_task(self):
        service = GenerationService(InMemoryGenerationRepository())
        background = _FakeBackground()
        request = ImageGenerationRequest(
            consultation_id="c1",
            face_asset_id="a1",
            prompt="jaw length bob",
            idempotency_key="route-dup-image",
        )

        first = await create_image_generation(request, background, service, object(), None)
        second = await create_image_generation(request, background, service, object(), None)

        self.assertEqual(first.generation_id, second.generation_id)
        self.assertEqual(len(background.tasks), 1)


if __name__ == "__main__":
    unittest.main()
