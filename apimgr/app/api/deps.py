"""의존성 주입(DI) — Service·Provider·Repository 를 라우터에 주입한다.

스캐폴드: 프로세스 수명 동안 인메모리 저장소 1개를 공유(실 DB 로드맵).
기본 Provider 는 Mock(규칙 §0.16).
"""

from __future__ import annotations

from functools import lru_cache

from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.generation_repository import InMemoryGenerationRepository
from app.services.generation_service import GenerationService
from app.services.webhook_service import WebhookService


@lru_cache(maxsize=1)
def get_generation_repository() -> InMemoryGenerationRepository:
    return InMemoryGenerationRepository()


@lru_cache(maxsize=1)
def get_generation_service() -> GenerationService:
    return GenerationService(get_generation_repository())


@lru_cache(maxsize=1)
def get_webhook_service() -> WebhookService:
    return WebhookService(get_generation_service())


def get_default_video_provider() -> MockVideoProvider:
    # 기본은 Mock. 실 Provider(PixVerse/fal)는 config.default_video_provider 로 로드맵 전환.
    return MockVideoProvider(MockScenario.SUCCESS)
