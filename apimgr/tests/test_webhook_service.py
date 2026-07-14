"""WebhookService 서명검증·중복안전·상태전이 테스트."""

import unittest

from app.core.security import compute_hmac_sha256
from app.domain.enums import GenerationStatus, ProviderJobStatus
from app.domain.errors import WebhookSignatureInvalid
from app.providers.video_generation.base import VideoGenerationInput
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.services.generation_service import GenerationService
from app.services.webhook_service import WebhookService, build_signed_message


def _valid_sig(event_ts: int, payload: bytes) -> str:
    # 서명은 event_ts + payload 결합에 대해 계산(webhook_service 규격).
    return compute_hmac_sha256("test-secret", build_signed_message(event_ts, payload))

_SECRET = "test-secret"


def _input(key: str) -> VideoGenerationInput:
    return VideoGenerationInput(
        image_asset_id="a1", prompt="p", duration_seconds=5,
        aspect_ratio="9:16", quality="720p", idempotency_key=key,
    )


class TestWebhookService(unittest.IsolatedAsyncioTestCase):
    async def _make(self):
        repo = InMemoryGenerationRepository()
        svc = GenerationService(repo)
        gen = await svc.create_video_generation(
            "gen-1", "c1", _input("k1"), MockVideoProvider(MockScenario.SUCCESS)
        )
        return svc, WebhookService(svc), gen

    async def test_invalid_signature_rejected(self):
        _svc, wh, gen = await self._make()
        payload = b'{"job":"x"}'
        with self.assertRaises(WebhookSignatureInvalid):
            wh.handle_status_event(
                secret=_SECRET, payload=payload, signature="bad",
                event_ts=1000, now_ts=1000, event_id="e1",
                provider="MOCK", external_job_id=gen.external_job_id,
                provider_status=ProviderJobStatus.PROCESSING,
            )

    async def test_stale_timestamp_rejected(self):
        _svc, wh, gen = await self._make()
        payload = b'{"job":"x"}'
        sig = _valid_sig(1000, payload)
        with self.assertRaises(WebhookSignatureInvalid):
            wh.handle_status_event(
                secret=_SECRET, payload=payload, signature=sig,
                event_ts=0, now_ts=100000, event_id="e2",
                provider="MOCK", external_job_id=gen.external_job_id,
                provider_status=ProviderJobStatus.PROCESSING,
            )

    async def test_valid_event_advances_status(self):
        _svc, wh, gen = await self._make()
        payload = b'{"job":"x"}'
        sig = _valid_sig(1000, payload)
        status = wh.handle_status_event(
            secret=_SECRET, payload=payload, signature=sig,
            event_ts=1000, now_ts=1000, event_id="e3",
            provider="MOCK", external_job_id=gen.external_job_id,
            provider_status=ProviderJobStatus.PROCESSING,
        )
        self.assertEqual(status, GenerationStatus.PROCESSING.value)

    async def test_out_of_order_webhook_not_permanently_lost(self):
        # 결함1 회귀: 작업 저장 전 도착한 webhook(external_job_id 미매칭)은
        # processed 로 박제되지 않아야 하며, 재전송 시 정상 처리돼야 한다.
        _svc, wh, gen = await self._make()
        payload = b'{"job":"x"}'
        sig = _valid_sig(1000, payload)
        # 1) 아직 저장 안 된 job 으로 먼저 도착 -> "" 반환, event_id 미기록.
        early = wh.handle_status_event(
            secret=_SECRET, payload=payload, signature=sig,
            event_ts=1000, now_ts=1000, event_id="reorder",
            provider="MOCK", external_job_id="not-yet-stored",
            provider_status=ProviderJobStatus.PROCESSING,
        )
        self.assertEqual(early, "")
        self.assertNotIn(("MOCK", "reorder"), wh._processed_event_ids)  # noqa: SLF001
        # 2) 같은 event_id 가 실제 job 으로 재전송 -> 정상 처리(무시되지 않음).
        later = wh.handle_status_event(
            secret=_SECRET, payload=payload, signature=sig,
            event_ts=1000, now_ts=1000, event_id="reorder",
            provider="MOCK", external_job_id=gen.external_job_id,
            provider_status=ProviderJobStatus.PROCESSING,
        )
        self.assertEqual(later, GenerationStatus.PROCESSING.value)

    async def test_duplicate_event_is_noop(self):
        _svc, wh, gen = await self._make()
        payload = b'{"job":"x"}'
        sig = _valid_sig(1000, payload)
        kw = dict(
            secret=_SECRET, payload=payload, signature=sig,
            event_ts=1000, now_ts=1000, event_id="dup",
            provider="MOCK", external_job_id=gen.external_job_id,
            provider_status=ProviderJobStatus.PROCESSING,
        )
        s1 = wh.handle_status_event(**kw)
        s2 = wh.handle_status_event(**kw)  # 동일 event_id -> 멱등
        self.assertEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
