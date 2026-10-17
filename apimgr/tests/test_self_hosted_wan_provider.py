"""Self-hosted Wan 영상 provider 테스트 — 외부 네트워크 없이 로컬 어댑터 계약 검증."""

import unittest
from decimal import Decimal
from typing import ClassVar
from unittest.mock import patch

from app.domain.enums import ErrorCode, ProviderJobStatus, ProviderName
from app.domain.errors import GenerationFailed
from app.providers.video_generation.base import VideoGenerationInput, VideoSourceImage
from app.providers.video_generation.self_hosted_wan import SelfHostedWanVideoProvider

_MP4_BYTES = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    b"\x00\x00\x00\x08free\x00\x00\x00\x08mdat"
)


def _input() -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="asset-1",
        prompt="slow salon camera push-in",
        duration_seconds=5,
        aspect_ratio="9:16",
        quality="720p",
        idempotency_key="wan-local-1",
        negative_prompt="distorted face",
        seed=42,
        source_image=VideoSourceImage(data=b"\x89PNG\r\n\x1a\n", content_type="image/png"),
    )


class _Response:
    def __init__(
        self,
        content: bytes = b"",
        status_code: int = 200,
        content_type: str = "application/json",
        json_body: dict[str, object] | None = None,
    ):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._json_body = json_body

    def json(self):
        if self._json_body is None:
            raise ValueError("invalid json")
        return self._json_body


class _Client:
    calls: ClassVar[list[dict[str, object]]] = []
    post_response = _Response(status_code=202, json_body={"job_id": "wan-job-1", "status": "PENDING"})
    get_responses: ClassVar[list[_Response]] = []

    def __init__(self, timeout: float):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, data=None, files=None):
        self.calls.append({"url": url, "data": data, "files": files, "timeout": self.timeout})
        return self.post_response

    async def get(self, url: str):
        self.calls.append({"url": url, "method": "GET", "timeout": self.timeout})
        if self.get_responses:
            return self.get_responses.pop(0)
        return _Response(status_code=200, json_body={"job_id": "wan-job-1", "status": "PROCESSING"})


class TestSelfHostedWanVideoProvider(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _Client.calls = []
        _Client.post_response = _Response(
            status_code=202,
            json_body={"job_id": "wan-job-1", "status": "PENDING"},
        )
        _Client.get_responses = []

    async def test_submit_registers_remote_job_without_asset_reference_payload(self):
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider(
                "http://127.0.0.1:8188",
                model="Wan-AI/Wan2.2-I2V-A14B-Diffusers",
                timeout_s=12,
            )
            result = await provider.submit(_input())

        self.assertEqual(result.provider, ProviderName.SELF_HOSTED_WAN)
        self.assertEqual(result.estimated_cost_usd, Decimal("0.00"))
        self.assertEqual(result.external_job_id, "wan-job-1")
        self.assertEqual(len(_Client.calls), 1)
        call = _Client.calls[0]
        self.assertEqual(call["url"], "http://127.0.0.1:8188/video/i2v")
        self.assertEqual(call["timeout"], 12)
        data = call["data"]
        self.assertIsInstance(data, dict)
        self.assertNotIn("image_asset_id", data)
        self.assertNotIn("storage_key", data)
        self.assertEqual(data["model"], "Wan-AI/Wan2.2-I2V-A14B-Diffusers")
        files = call["files"]
        self.assertIsInstance(files, dict)
        self.assertIn("image", files)

    async def test_get_status_fetches_output_when_remote_job_succeeds(self):
        _Client.get_responses = [
            _Response(status_code=200, json_body={"job_id": "wan-job-1", "status": "PROCESSING"}),
            _Response(status_code=200, json_body={"job_id": "wan-job-1", "status": "SUCCEEDED"}),
            _Response(content=_MP4_BYTES, status_code=200, content_type="video/mp4"),
        ]
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider("http://127.0.0.1:8188")
            status = await provider.get_status("wan-job-1")
            self.assertEqual(status.status, ProviderJobStatus.PROCESSING)
            self.assertIsNone(status.output_bytes)

            status = await provider.get_status("wan-job-1")

        self.assertEqual(status.status, ProviderJobStatus.SUCCEEDED)
        self.assertEqual(status.output_bytes, _MP4_BYTES)
        self.assertIsNone(status.output_url)
        get_urls = [call["url"] for call in _Client.calls if call.get("method") == "GET"]
        self.assertEqual(
            get_urls,
            [
                "http://127.0.0.1:8188/video/i2v/wan-job-1",
                "http://127.0.0.1:8188/video/i2v/wan-job-1",
                "http://127.0.0.1:8188/video/i2v/wan-job-1/output",
            ],
        )

    async def test_legacy_direct_mp4_response_still_succeeds(self):
        _Client.post_response = _Response(content=_MP4_BYTES, status_code=200, content_type="video/mp4")
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider("http://127.0.0.1:8188")
            result = await provider.submit(_input())

        status = await provider.get_status(result.external_job_id)
        self.assertEqual(status.status, ProviderJobStatus.SUCCEEDED)
        self.assertEqual(status.output_bytes, _MP4_BYTES)
        self.assertIsNone(status.output_url)

    async def test_rejects_non_local_base_url(self):
        with self.assertRaises(GenerationFailed):
            SelfHostedWanVideoProvider("https://example.com")

    async def test_rejects_non_mp4_response(self):
        _Client.post_response = _Response(b"not-a-video", content_type="video/mp4")
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider("http://localhost:8188")
            with self.assertRaises(GenerationFailed):
                await provider.submit(_input())

    async def test_processing_when_output_is_not_available(self):
        _Client.get_responses = [
            _Response(status_code=200, json_body={"job_id": "wan-job-1", "status": "PROCESSING"}),
        ]
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider("http://localhost:8188")
            status = await provider.get_status("missing-job")
        self.assertEqual(status.status, ProviderJobStatus.PROCESSING)

    async def test_remote_failed_status_preserves_error_code(self):
        _Client.get_responses = [
            _Response(
                status_code=200,
                json_body={
                    "job_id": "wan-job-1",
                    "status": "FAILED",
                    "error_code": "GENERATION_FAILED",
                },
            ),
        ]
        with patch("app.providers.video_generation.self_hosted_wan.httpx.AsyncClient", _Client):
            provider = SelfHostedWanVideoProvider("http://localhost:8188")
            status = await provider.get_status("wan-job-1")
        self.assertEqual(status.status, ProviderJobStatus.FAILED)
        self.assertEqual(status.error_code, ErrorCode.GENERATION_FAILED)


if __name__ == "__main__":
    unittest.main()
