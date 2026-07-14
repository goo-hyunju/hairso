"""환경설정 로딩 (stdlib os.environ 기반 — pydantic-settings 미의존으로 stdlib 계층 유지).

자격증명·모델명은 코드에 하드코딩하지 않고 여기(환경변수)에서만 읽는다(규칙 §4.8/§4.18).
실제 값은 .env / secret 관리로 주입한다. 값 미주입 시 안전한 기본(빈 문자열·MOCK)을 쓴다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


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

    # 모델 토큰 (Registry — env 로만, 하드코딩 금지). 미설정 시 빈 값.
    pixverse_video_model: str = field(default_factory=lambda: _get("PIXVERSE_VIDEO_MODEL"))
    fal_wan_video_model: str = field(default_factory=lambda: _get("FAL_WAN_VIDEO_MODEL"))
    gemini_image_model: str = field(default_factory=lambda: _get("GEMINI_IMAGE_MODEL"))


def get_settings() -> Settings:
    """설정 인스턴스를 만든다(호출 시점의 환경변수 스냅샷)."""
    return Settings()
