"""의존성 주입(DI) — Service·Provider·Repository 를 라우터에 주입한다.

Repository: DATABASE_URL 설정 시 Supabase(psycopg), 없으면 InMemory(스캐폴드/테스트).
기본 Provider 는 Mock(규칙 §0.16).
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.generation_repository import (
    GenerationRepository,
    InMemoryGenerationRepository,
)
from app.services.generation_service import GenerationService
from app.services.webhook_service import WebhookService


@lru_cache(maxsize=1)
def get_generation_repository() -> GenerationRepository:
    # DATABASE_URL 이 있으면 실 DB(Supabase), 없으면 인메모리(테스트·오프라인).
    # 지연 import: psycopg 미설치 환경에서도 인메모리 경로가 깨지지 않게 한다.
    settings = get_settings()
    if settings.database_url:
        from app.repositories.supabase_generation_repository import (
            SupabaseGenerationRepository,
        )

        return SupabaseGenerationRepository(settings.database_url)
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
