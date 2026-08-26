"""환경설정 로딩 (stdlib os.environ 기반 — pydantic-settings 미의존으로 stdlib 계층 유지).

자격증명·모델명은 코드에 하드코딩하지 않고 여기(환경변수)에서만 읽는다(규칙 §4.8/§4.18).
실제 값은 .env / secret 관리로 주입한다. 값 미주입 시 안전한 기본(빈 문자열·MOCK)을 쓴다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """런타임 설정. 비밀값은 로그로 출력하지 않는다(규칙 §0.14)."""

    # 인프라
    database_url: str = field(default_factory=lambda: _get("DATABASE_URL"))
    jwt_secret: str = field(default_factory=lambda: _get("JWT_SECRET"))

    # Supabase Auth (JWKS ES256 토큰 검증). SUPABASE_URL 미설정 시 인증 비활성(익명만).
    supabase_url: str = field(default_factory=lambda: _get("SUPABASE_URL"))
    jwt_audience: str = field(default_factory=lambda: _get("JWT_AUDIENCE", "authenticated"))

    # 스토리지 (R2)
    storage_access_key: str = field(default_factory=lambda: _get("STORAGE_ACCESS_KEY"))
    storage_secret_key: str = field(default_factory=lambda: _get("STORAGE_SECRET_KEY"))

    # 외부 AI Provider (모델명도 env — 하드코딩 금지)
    gemini_api_key: str = field(default_factory=lambda: _get("GEMINI_API_KEY"))
    pixverse_api_key: str = field(default_factory=lambda: _get("PIXVERSE_API_KEY"))
    pixverse_webhook_secret: str = field(default_factory=lambda: _get("PIXVERSE_WEBHOOK_SECRET"))
    fal_key: str = field(default_factory=lambda: _get("FAL_KEY"))
    wan_api_key: str = field(default_factory=lambda: _get("WAN_API_KEY"))

    # Provider 선택 (기본 Mock — 규칙 §0.16: 테스트 기본은 Mock)
    default_video_provider: str = field(default_factory=lambda: _get("DEFAULT_VIDEO_PROVIDER", "MOCK"))
    default_image_provider: str = field(default_factory=lambda: _get("DEFAULT_IMAGE_PROVIDER", "MOCK"))
    default_analysis_provider: str = field(default_factory=lambda: _get("DEFAULT_ANALYSIS_PROVIDER", "MOCK"))
    default_studio_draft_provider: str = field(
        default_factory=lambda: _get("DEFAULT_STUDIO_DRAFT_PROVIDER", "MOCK")
    )

    # 로컬 이미지 생성(LOCAL Provider) — 별도 추론 서비스(ml/serve.py) URL.
    local_inference_url: str = field(default_factory=lambda: _get("LOCAL_INFERENCE_URL", "http://127.0.0.1:8188"))
    # 로컬 영상 생성(SELF_HOSTED_WAN Provider) — 별도 추론 서비스(ml/serve.py 또는 호환 서버) URL.
    local_video_inference_url: str = field(
        default_factory=lambda: _get("LOCAL_VIDEO_INFERENCE_URL", "http://127.0.0.1:8188")
    )
    local_video_endpoint_path: str = field(
        default_factory=lambda: _get("LOCAL_VIDEO_ENDPOINT_PATH", "/video/i2v")
    )
    local_video_timeout_seconds: int = field(
        default_factory=lambda: _get_int("LOCAL_VIDEO_TIMEOUT_SECONDS", 900)
    )
    self_hosted_wan_video_model: str = field(
        default_factory=lambda: _get("SELF_HOSTED_WAN_VIDEO_MODEL")
    )
    # 로컬 텍스트 초안 생성(Ollama). 모델명은 env 로만 주입하고, 기본값은 Mock fallback.
    ollama_base_url: str = field(default_factory=lambda: _get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    ollama_studio_draft_model: str = field(default_factory=lambda: _get("OLLAMA_STUDIO_DRAFT_MODEL"))
    ollama_timeout_seconds: int = field(default_factory=lambda: _get_int("OLLAMA_TIMEOUT_SECONDS", 60))

    # 에셋 저장소 — LOCAL_DISK(기본, 자격증명 불필요) 또는 SUPABASE(service_role/secret 키 필요).
    # 로컬 디스크 루트: 고객 얼굴/결과가 저장되므로 저장소 밖 경로 사용(§4.13 — repo 밖).
    asset_store_backend: str = field(default_factory=lambda: _get("ASSET_STORE_BACKEND", "LOCAL_DISK"))
    asset_local_root: str = field(default_factory=lambda: _get("ASSET_LOCAL_ROOT", ""))

    # Supabase Storage (ASSET_STORE_BACKEND=SUPABASE 일 때 서버측 업로드용).
    # secret 키(sb_secret_... = service_role 역할)는 로그 출력 금지(§0.14). 실값은 .env 만.
    supabase_secret_key: str = field(default_factory=lambda: _get("SUPABASE_SECRET_KEY"))
    supabase_storage_bucket: str = field(default_factory=lambda: _get("SUPABASE_STORAGE_BUCKET", "hairview-assets"))

    # 모델 토큰 (Registry — env 로만, 하드코딩 금지). 미설정 시 빈 값.
    pixverse_video_model: str = field(default_factory=lambda: _get("PIXVERSE_VIDEO_MODEL"))
    fal_wan_video_model: str = field(default_factory=lambda: _get("FAL_WAN_VIDEO_MODEL"))
    gemini_image_model: str = field(default_factory=lambda: _get("GEMINI_IMAGE_MODEL"))

    # Studio 저장 설정(비밀 아님). 실제 바이트 저장 위치는 AssetStore 설정이 결정하고,
    # Studio 는 어떤 profile/prefix/retention 정책으로 결과를 보관할지만 기록한다.
    studio_storage_profile_name: str = field(
        default_factory=lambda: _get("STUDIO_STORAGE_PROFILE_NAME", "local-dev")
    )
    studio_output_prefix: str = field(
        default_factory=lambda: _get("STUDIO_OUTPUT_PREFIX", "studio/outputs")
    )
    studio_output_retention_days: int = field(
        default_factory=lambda: _get_int("STUDIO_OUTPUT_RETENTION_DAYS", 30)
    )


def get_settings() -> Settings:
    """설정 인스턴스를 만든다(호출 시점의 환경변수 스냅샷)."""
    return Settings()
