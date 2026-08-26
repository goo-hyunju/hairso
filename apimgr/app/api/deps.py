"""의존성 주입(DI) — Service·Provider·Repository 를 라우터에 주입한다.

Repository: DATABASE_URL 설정 시 Supabase(psycopg), 없으면 InMemory(스캐폴드/테스트).
기본 Provider 는 Mock(규칙 §0.16).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request

from app.api.auth import SupabaseJWTVerifier
from app.core.config import get_settings
from app.providers.image_generation.base import ImageProvider
from app.providers.storage.base import AssetStore
from app.providers.studio_draft.base import StudioDraftProvider, StudioDraftProviderError
from app.providers.studio_draft.mock import MockStudioDraftProvider
from app.providers.studio_draft.ollama import OllamaStudioDraftProvider
from app.providers.storage.local_disk import LocalDiskAssetStore
from app.providers.video_generation.base import VideoProvider
from app.providers.video_generation.mock import MockScenario, MockVideoProvider
from app.repositories.asset_repository import AssetRepository, InMemoryAssetRepository
from app.repositories.generation_repository import (
    GenerationRepository,
    InMemoryGenerationRepository,
)
from app.repositories.studio_repository import InMemoryStudioRepository, StudioRepository
from app.services.asset_service import AssetService
from app.services.generation_service import GenerationService
from app.services.studio_service import StudioService
from app.services.webhook_service import WebhookService

# ASSET_LOCAL_ROOT 미설정 시 기본: 저장소(repo) 밖 rengoo/models(§4.13 — 고객 얼굴/결과 repo 밖).
# deps.py = apimgr/app/api/deps.py → parents[4] = rengoo.
_DEFAULT_ASSET_ROOT = Path(__file__).resolve().parents[4] / "models"


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


def get_default_video_provider() -> VideoProvider:
    """기본 영상 Provider.

    MOCK 은 테스트/개발 기본값이다. SELF_HOSTED_WAN 은 명시 opt-in 로컬 추론 서버만 호출한다.
    아직 구현하지 않은 원격 provider 를 설정하면 조용한 Mock fallback 대신 fail-closed 한다.
    """
    s = get_settings()
    provider = s.default_video_provider.upper()
    if provider == "MOCK":
        return MockVideoProvider(MockScenario.SUCCESS)
    if provider == "SELF_HOSTED_WAN":
        from app.providers.video_generation.self_hosted_wan import SelfHostedWanVideoProvider

        return SelfHostedWanVideoProvider(
            s.local_video_inference_url,
            model=s.self_hosted_wan_video_model,
            endpoint_path=s.local_video_endpoint_path,
            timeout_s=float(s.local_video_timeout_seconds),
        )
    raise RuntimeError(f"DEFAULT_VIDEO_PROVIDER={provider} is not implemented")


@lru_cache(maxsize=1)
def get_asset_store() -> AssetStore:
    """에셋 바이트 저장소 — SUPABASE(키 필요) 또는 LOCAL_DISK(기본, 자격증명 불필요)."""
    s = get_settings()
    if s.asset_store_backend.upper() == "SUPABASE":
        if not (s.supabase_url and s.supabase_secret_key):
            raise RuntimeError("ASSET_STORE_BACKEND=SUPABASE 이나 SUPABASE_URL/SUPABASE_SECRET_KEY 미설정")
        from app.providers.storage.supabase import SupabaseAssetStore

        return SupabaseAssetStore(s.supabase_url, s.supabase_secret_key, s.supabase_storage_bucket)
    return LocalDiskAssetStore(s.asset_local_root or str(_DEFAULT_ASSET_ROOT))


@lru_cache(maxsize=1)
def get_asset_repository() -> AssetRepository:
    # DATABASE_URL 있으면 실 DB(Supabase assets), 없으면 인메모리(테스트·오프라인).
    s = get_settings()
    if s.database_url:
        from app.repositories.supabase_asset_repository import SupabaseAssetRepository

        return SupabaseAssetRepository(s.database_url)
    return InMemoryAssetRepository()


@lru_cache(maxsize=1)
def get_asset_service() -> AssetService:
    s = get_settings()
    return AssetService(
        get_asset_store(),
        get_asset_repository(),
        generated_video_prefix=s.studio_output_prefix,
        generated_video_expiry_days=s.studio_output_retention_days,
    )


@lru_cache(maxsize=1)
def get_studio_repository() -> StudioRepository:
    s = get_settings()
    if s.database_url:
        from app.repositories.supabase_studio_repository import SupabaseStudioRepository

        return SupabaseStudioRepository(s.database_url)
    return InMemoryStudioRepository()


@lru_cache(maxsize=1)
def get_studio_draft_provider() -> StudioDraftProvider:
    """Studio script/storyboard 초안 provider.

    기본은 Mock 이다. OLLAMA 는 로컬 서버와 모델이 준비된 경우에만 사용하고,
    설정 오류는 local dev 흐름을 깨지 않도록 Mock 으로 되돌린다.
    """
    s = get_settings()
    if s.default_studio_draft_provider.upper() == "OLLAMA":
        try:
            return OllamaStudioDraftProvider(
                s.ollama_base_url,
                s.ollama_studio_draft_model,
                float(s.ollama_timeout_seconds),
            )
        except StudioDraftProviderError:
            return MockStudioDraftProvider()
    return MockStudioDraftProvider()


@lru_cache(maxsize=1)
def get_studio_service() -> StudioService:
    return StudioService(
        get_studio_repository(),
        get_generation_service(),
        get_asset_service(),
        get_studio_draft_provider(),
    )



def get_default_image_provider() -> ImageProvider:
    """기본 이미지 Provider — LOCAL_SD(로컬 추론 서비스) 또는 Mock."""
    s = get_settings()
    if s.default_image_provider.upper() == "LOCAL_SD":
        from app.providers.image_generation.local import LocalImageProvider

        return LocalImageProvider(get_asset_store(), s.local_inference_url)
    from app.providers.image_generation.mock import MockImageProvider

    return MockImageProvider(MockScenario.SUCCESS, processing_polls=0, store=get_asset_store())


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

