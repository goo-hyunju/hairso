"""PixVerse Platform API Provider — [미구현-로드맵] 스텁.

실제 PixVerse API 스펙(엔드포인트·필드·모델명)은 외부 미검증 정보다.
이 파일은 계약 형태만 잡은 스텁이며, 실 연동은 로드맵(4주차)이다. 실 호출 코드 없음.
"""

from __future__ import annotations

from app.domain.enums import ProviderName
from app.providers.video_generation.base import (
    VideoGenerationInput,
    VideoProvider,
    VideoStatusResult,
    VideoSubmissionResult,
)

# unverified — 실 PixVerse API 스펙 미확인 (기획서 §8.3). 하드코딩 금지: 모델명은 env(config)로.
#   흐름(기획서 §8.3): 이미지 업로드 -> img_id -> i2v 요청 -> video_id -> webhook/폴링 -> 다운로드
#   필수 헤더: API Key + 요청별 Ai-trace-id (내부 idempotency_key 와 별도 저장)


class PixVerseVideoProvider(VideoProvider):
    """[미구현-로드맵] PixVerse V6 i2v. 실 API 미연동."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key  # 로그 출력 금지(§0.14)
        self._model = model  # env 주입 — 하드코딩 아님

    async def submit(self, data: VideoGenerationInput) -> VideoSubmissionResult:
        raise NotImplementedError(
            "PixVerse 실 연동은 로드맵(4주차). 현재는 MockVideoProvider 를 사용한다."
        )

    async def get_status(self, external_job_id: str) -> VideoStatusResult:
        raise NotImplementedError(
            "PixVerse 실 연동은 로드맵(4주차). 현재는 MockVideoProvider 를 사용한다."
        )

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.PIXVERSE
