"""에셋 서비스 — 바이트(AssetStore) + 메타데이터(AssetRepository) 오케스트레이션.

업로드: 서버측 재검증(§4.14 — 확장자만 믿지 않고 실제 시그니처 확인) → 저장 → 메타 기록.
결과 등록: provider 가 저장한 출력 바이트를 GENERATED_IMAGE 에셋으로 메타 기록.
얼굴 원본 바이트·storage_key 는 로그에 남기지 않는다(§0.15).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from app.domain.enums import ErrorCode
from app.domain.errors import DomainError
from app.domain.models import Asset, _utcnow
from app.providers.storage.base import AssetStore
from app.repositories.asset_repository import AssetRepository

# 허용 이미지 시그니처(매직 바이트) — 확장자·mime 헤더만 믿지 않는다(§4.14).
_SIGNATURES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",  # RIFF....WEBP
}
_MAX_BYTES = 15 * 1024 * 1024  # 15MB 상한(얼굴 사진)

# 만료 정책(§4.13): 얼굴 원본은 짧게, 생성 결과는 조금 길게.
_EXPIRY = {"FACE_SOURCE": timedelta(hours=24), "GENERATED_IMAGE": timedelta(days=7)}


class AssetValidationError(DomainError):
    error_code = ErrorCode.ASSET_INVALID
    retryable = False


def _detect_mime(data: bytes) -> str | None:
    for mime, sig in _SIGNATURES.items():
        if mime == "image/webp":
            if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                return mime
        elif data.startswith(sig):
            return mime
    return None


class AssetService:
    def __init__(self, store: AssetStore, repo: AssetRepository) -> None:
        self._store = store
        self._repo = repo

    def upload_face(
        self,
        data: bytes,
        owner_id: str | None = None,
        consultation_id: str | None = None,
    ) -> Asset:
        """얼굴 원본 업로드 — 서버 재검증 후 저장. storage_key 는 provider 규약과 일치(face/{id}.png)."""
        if not data:
            raise AssetValidationError("빈 파일")
        if len(data) > _MAX_BYTES:
            raise AssetValidationError("파일이 너무 큽니다")
        mime = _detect_mime(data)
        if mime is None:
            raise AssetValidationError("지원하지 않는 이미지 형식")

        asset_id = str(uuid.uuid4())
        storage_key = f"face/{asset_id}.png"  # LocalImageProvider.face_key 와 동일 규약
        self._store.save(storage_key, data, mime)
        asset = Asset(
            id=asset_id,
            owner_type="CUSTOMER",
            asset_type="FACE_SOURCE",
            storage_key=storage_key,
            mime_type=mime,
            byte_size=len(data),
            owner_id=owner_id,
            consultation_id=consultation_id,
            sha256=hashlib.sha256(data).hexdigest(),
            expires_at=_utcnow() + _EXPIRY["FACE_SOURCE"],
        )
        return self._repo.save(asset)

    def register_generated_image(
        self, storage_key: str, consultation_id: str | None = None
    ) -> Asset:
        """provider 가 이미 저장한 출력 바이트를 GENERATED_IMAGE 에셋으로 메타 기록."""
        data = self._store.load(storage_key)  # size/hash 계산용
        asset = Asset(
            id=str(uuid.uuid4()),
            owner_type="SYSTEM",
            asset_type="GENERATED_IMAGE",
            storage_key=storage_key,
            mime_type="image/png",
            byte_size=len(data),
            consultation_id=consultation_id,
            sha256=hashlib.sha256(data).hexdigest(),
            expires_at=_utcnow() + _EXPIRY["GENERATED_IMAGE"],
        )
        return self._repo.save(asset)

    def get_bytes(self, asset_id: str) -> tuple[bytes, str] | None:
        """다운로드용 — (바이트, mime). 없으면 None."""
        asset = self._repo.get(asset_id)
        if asset is None or asset.status != "ACTIVE":
            return None
        try:
            return self._store.load(asset.storage_key), asset.mime_type
        except FileNotFoundError:
            return None
