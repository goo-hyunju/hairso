"""생성 작업 폴링 Worker 골격 — [일부구현·검증완료 / 실 후처리 미구현-로드맵].

advance_once: 한 작업을 1회 폴링해 상태를 반영한다(결정적, 테스트 가능).
    - provider 상태를 내부 상태로 반영(apply_provider_status).
    - VIDEO 가 POST_PROCESSING 에 도달하면 후처리 단계:
        · 결과 URL 다운로드 실패 -> FAILED(DOWNLOAD_FAILED)
        · 성공 -> SUCCEEDED(§13 'worker 완료 시 SUCCEEDED')
실 다운로드·R2 저장·FFmpeg·만료 삭제는 로드맵(실 스토리지 필요) — 여기서는 mock URL 판별만.

실패/완료는 service 를 경유(상태머신 가드 + 전체 영속). 직접 gen.status 대입 안 함(역행·false green 방지).
"""

from __future__ import annotations

import math
import os

from app.core.config import get_settings
from app.domain.enums import ErrorCode, GenerationStatus, GenerationType
from app.domain.errors import DownloadFailed
from app.domain.models import Generation
from app.providers.video_generation.base import VideoProvider
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService

_MOCK_VIDEO_BYTES = (
    b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    b"\x00\x00\x00\x08free\x00\x00\x00\x08mdat"
)


def video_polling_config() -> tuple[float, int]:
    """영상 provider polling 간격/횟수.

    테스트와 Mock 개발은 `MOCK_ADVANCE_INTERVAL_SEC=0`으로 빠르게 끝내고, self-hosted Wan은
    `LOCAL_VIDEO_TIMEOUT_SECONDS` 범위 안에서 긴 작업을 기다린다.
    """
    interval = _float_env(
        "VIDEO_GENERATION_POLL_INTERVAL_SECONDS",
        _float_env("MOCK_ADVANCE_INTERVAL_SEC", 1.0),
    )
    interval = max(0.0, interval)
    configured_max_polls = _int_env("VIDEO_GENERATION_MAX_POLLS", 0)
    if configured_max_polls > 0:
        return interval, configured_max_polls
    if interval <= 0:
        return interval, 8
    timeout_seconds = max(1, get_settings().local_video_timeout_seconds)
    return interval, max(8, math.ceil(timeout_seconds / interval) + 6)


class GenerationWorker:
    def __init__(
        self,
        service: GenerationService,
        asset_service: AssetService | None = None,
    ) -> None:
        self._service = service
        self._asset_service = asset_service

    async def advance_once(self, gen: Generation, provider: VideoProvider) -> Generation:
        """작업을 1회 폴링해 내부 상태를 전진시킨다.

        provider FAILED(ASYNC_FAIL)면 error_code 가 보존된다. POST_PROCESSING 도달 후에만
        다운로드 성공/실패를 판정한다(그 전 상태에서 우연한 output_url 로 오판하지 않음).
        """
        status = await provider.get_status(gen.external_job_id or "")
        gen = self._service.apply_provider_status(
            gen, status.status, GenerationType.VIDEO, error_code=status.error_code
        )
        # 후처리는 내부 POST_PROCESSING 도달 이후에만 판정한다(#7).
        if gen.status is GenerationStatus.POST_PROCESSING:
            # 유효한 결과 URL 이 있어야 성공 — 부재(None/빈문자열)·실패 마커는 다운로드 실패로 처리(#4).
            if (
                status.output_bytes is None
                and (not status.output_url or status.output_url == "mock://download-fail")
            ):
                self._service.fail_generation(
                    gen, GenerationType.VIDEO, ErrorCode.DOWNLOAD_FAILED, str(DownloadFailed())
                )
            else:
                if status.output_bytes is None and not status.output_url.startswith("mock://"):
                    self._service.fail_generation(
                        gen,
                        GenerationType.VIDEO,
                        ErrorCode.DOWNLOAD_FAILED,
                        str(DownloadFailed()),
                    )
                    return gen

                # provider MP4 바이트 또는 Mock MP4 fixture 저장 -> SUCCEEDED(#8).
                output_asset_id = "mock-output-asset"
                if self._asset_service is not None:
                    video_bytes = status.output_bytes or _MOCK_VIDEO_BYTES
                    asset = self._asset_service.register_generated_video(
                        video_bytes,
                        owner_id=gen.created_by,
                        consultation_id=gen.consultation_id,
                    )
                    output_asset_id = asset.id
                self._service.complete_generation(
                    gen, GenerationType.VIDEO, output_asset_id=output_asset_id
                )
        return gen


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default
