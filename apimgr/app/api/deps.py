"""의존성 주입(DI) — Service·Provider·Repository 를 라우터에 주입한다.

Repository: DATABASE_URL 설정 시 Supabase(psycopg), 없으면 InMemory(스캐폴드/테스트).
기본 Provider 는 Mock(규칙 §0.16).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, Request

from app.api.auth import SupabaseJWTVerifier
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


@lru_cache(maxsize=1)
def get_jwt_verifier() -> SupabaseJWTVerifier | None:
    # SUPABASE_URL 미설정 시 인증 비활성(None) — 토큰 검증 불가.
    settings = get_settings()
    if not settings.supabase_url:
        return None
    return SupabaseJWTVerifier(settings.supabase_url, settings.jwt_audience)


def get_optional_user(request: Request) -> str | None:
    """선택적 인증(§ 결정: 점진적). Bearer 토큰이 있으면 검증해 user_id(sub)를 반환하고,
    없으면 None(익명 허용).

    토큰이 있으나 무효/검증불가면 401 — 위조 토큰을 익명으로 통과시키지 않는다(§11 보안).
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer ") :].strip()
    if not token:
        return None
    verifier = get_jwt_verifier()
    if verifier is None:
        # 서버에 Supabase URL 미설정 → 토큰을 신뢰할 수 없다.
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    try:
        payload = verifier.verify(token)
    except Exception:
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")
    sub = payload.get("sub")
    return str(sub) if sub is not None else None
