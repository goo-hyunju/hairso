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

from app.domain.enums import ErrorCode, GenerationStatus, GenerationType
from app.domain.errors import DownloadFailed
from app.domain.models import Generation
from app.providers.video_generation.base import VideoProvider
from app.services.generation_service import GenerationService


class GenerationWorker:
    def __init__(self, service: GenerationService) -> None:
        self._service = service

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
            if not status.output_url or status.output_url == "mock://download-fail":
                self._service.fail_generation(
                    gen, GenerationType.VIDEO, ErrorCode.DOWNLOAD_FAILED, str(DownloadFailed())
                )
            else:
                # 다운로드·R2·FFmpeg(로드맵) 성공 가정 -> SUCCEEDED(#8).
                self._service.complete_generation(
                    gen, GenerationType.VIDEO, output_asset_id="mock-output-asset"
                )
        return gen
