"""Self-hosted Wan/CogVideo 스타일 로컬 영상 Provider.

이 provider 는 외부 유료 API 가 아니라 같은 개발 머신 또는 내부 compose 네트워크의 로컬 추론
서비스를 호출한다. 고객 이미지 URL, signed URL, storage key, Base64 문자열은 보내지 않고,
필요 시 backend-only 이미지 바이트만 multipart 로 전달한다.

예상 로컬 서비스 계약:

POST /video/i2v
  form: prompt, duration_seconds, aspect_ratio, quality, idempotency_key, model?, negative_prompt?, seed?
  file: image?  (image-to-video일 때만)
  response: video/mp4 bytes
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlparse

import httpx

from app.core.media import is_probable_mp4
from app.domain.enums import ProviderJobStatus, ProviderName
from app.domain.errors import GenerationFailed
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoStatusResult,
    VideoSubmissionResult,
)

_LOCAL_HOSTS = {
    "127.0.0.1",
    "localhost",
    "::1",
    "host.docker.internal",
    "ml",
}
_ZERO_COST = Decimal("0.00")


class SelfHostedWanVideoProvider(VideoProvider):
    """로컬 Wan 2.x 계열 또는 호환 I2V/T2V 추론 서비스 어댑터."""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "",
        endpoint_path: str = "/video/i2v",
        timeout_s: float = 900.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint_path = endpoint_path if endpoint_path.startswith("/") else f"/{endpoint_path}"
        self._model = model.strip()
        self._timeout = timeout_s
        self._outputs: dict[str, bytes] = {}
        self._assert_local_url()

    def _assert_local_url(self) -> None:
        parsed = urlparse(self._base_url)
        if parsed.scheme not in {"http", "https"}:
            raise GenerationFailed("self-hosted video provider URL must be http(s)")
        host = parsed.hostname or ""
        if host not in _LOCAL_HOSTS:
            raise GenerationFailed("self-hosted video provider must use a local host")

    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        job_id = f"self-hosted-wan-{data.idempotency_key}"
        form: dict[str, str] = {
            "prompt": data.prompt,
            "duration_seconds": str(data.duration_seconds),
            "aspect_ratio": data.aspect_ratio,
            "quality": data.quality,
            "idempotency_key": data.idempotency_key,
        }
        if data.negative_prompt:
            form["negative_prompt"] = data.negative_prompt
        if data.seed is not None:
            form["seed"] = str(data.seed)
        if self._model:
            form["model"] = self._model

        files = None
        if data.source_image is not None:
            files = {
                "image": (
                    "source",
                    data.source_image.data,
                    data.source_image.content_type,
                )
            }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}{self._endpoint_path}",
                    data=form,
                    files=files,
                )
        except httpx.HTTPError as exc:
            raise GenerationFailed("self-hosted video request failed") from exc

        if resp.status_code != 200:
            raise GenerationFailed(f"self-hosted video status {resp.status_code}")
        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type and content_type != "video/mp4":
            raise GenerationFailed("self-hosted video response is not mp4")
        if not is_probable_mp4(resp.content):
            raise GenerationFailed("self-hosted video response is not a valid mp4 container")

        self._outputs[job_id] = resp.content
        return VideoSubmissionResult(
            provider=ProviderName.SELF_HOSTED_WAN,
            external_job_id=job_id,
            estimated_cost_usd=_ZERO_COST,
        )

    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        output = self._outputs.get(external_job_id)
        if output is None:
            return VideoStatusResult(status=ProviderJobStatus.PROCESSING)
        return VideoStatusResult(
            status=ProviderJobStatus.SUCCEEDED,
            output_bytes=output,
        )
