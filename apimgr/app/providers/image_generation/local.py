"""로컬 이미지 생성 Provider — 로컬 SD inpainting 추론 서비스(ml/serve.py)를 HTTP로 호출.

로컬 생성은 동기·수초이므로 submit 에서 추론+결과저장까지 마치고, get_status 는 저장된 결과를
즉시 SUCCEEDED 로 보고한다(외부 비동기 Provider 와 달리 폴링 대기 없음 — 인터페이스는 동일 유지).

얼굴 바이트는 AssetStore 에서만 읽고 로그에 남기지 않는다(§0.15). 비용은 로컬이라 0.00(요금 없음).

⚠️ (1)단계 임시: provider 이름을 MOCK 으로 보고한다. 정식 `LOCAL_SD` enum + DB check 제약 +
    FE/BE 계약 parity 는 (2)단계에서 마이그레이션과 함께(§4.19). 여기선 DB·계약을 건드리지 않는다.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from app.domain.enums import ProviderJobStatus, ProviderName
from app.domain.errors import GenerationFailed
from app.providers.image_generation.base import (
    ImageGenerationInput,
    ImageProvider,
    ImageStatusResult,
    ImageSubmissionResult,
)
from app.providers.storage.base import AssetStore


class LocalImageProvider(ImageProvider):
    def __init__(
        self,
        store: AssetStore,
        base_url: str,
        steps: int = 30,
        timeout_s: float = 180.0,
    ) -> None:
        self._store = store
        self._base_url = base_url.rstrip("/")
        self._steps = steps
        self._timeout = timeout_s
        # 동일 프로세스 내 submit→get_status 연결용(로컬 동기). 실 비동기/멀티프로세스는 (2)에서 DB.
        self._outputs: dict[str, str] = {}

    @staticmethod
    def face_key(face_asset_id: str) -> str:
        """얼굴 에셋의 저장 키 규약. 업로드 경로가 이 키로 얼굴을 저장한다((2)에서 정식 배선)."""
        return f"face/{face_asset_id}.png"

    @staticmethod
    def output_key(external_job_id: str) -> str:
        return f"generated/{external_job_id}.png"

    async def submit(self, data: ImageGenerationInput) -> ImageSubmissionResult:
        try:
            face_bytes = self._store.load(self.face_key(data.face_asset_id))
        except FileNotFoundError as exc:
            # (2)에서 ASSET_NOT_FOUND 로 세분화. 지금은 생성 실패로 처리.
            raise GenerationFailed("face asset not found") from exc

        job_id = f"local-image-{data.idempotency_key}-{data.variant.value}"
        form: dict[str, str] = {"prompt": data.prompt, "steps": str(self._steps)}
        if data.negative_prompt:
            form["negative_prompt"] = data.negative_prompt

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/restyle",
                    files={"image": ("face.png", face_bytes, "image/png")},
                    data=form,
                )
        except httpx.HTTPError as exc:
            raise GenerationFailed("local inference request failed") from exc
        if resp.status_code != 200:
            raise GenerationFailed(f"local inference status {resp.status_code}")

        out_key = self.output_key(job_id)
        self._store.save(out_key, resp.content, "image/png")
        self._outputs[job_id] = out_key
        return ImageSubmissionResult(
            provider=ProviderName.MOCK,  # (1) 임시 — (2)에서 LOCAL_SD
            external_job_id=job_id,
            estimated_cost_usd=Decimal("0.00"),
        )

    async def get_status(self, external_job_id: str) -> ImageStatusResult:
        out_key = self._outputs.get(external_job_id)
        if out_key is None:
            return ImageStatusResult(status=ProviderJobStatus.PROCESSING)
        return ImageStatusResult(status=ProviderJobStatus.SUCCEEDED, output_url=out_key)
