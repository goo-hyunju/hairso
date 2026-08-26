"""에셋 서비스 — 바이트(AssetStore) + 메타데이터(AssetRepository) 오케스트레이션.

업로드: 서버측 재검증(§4.14 — 확장자만 믿지 않고 실제 시그니처 확인) → 저장 → 메타 기록.
결과 등록: provider 가 저장한 출력 바이트를 GENERATED_IMAGE 에셋으로 메타 기록.
얼굴 원본 바이트·storage_key 는 로그에 남기지 않는다(§0.15).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from pathlib import PurePosixPath

from app.core.media import is_probable_mp4
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
_DEFAULT_VIDEO_PREFIX = "video"


class AssetValidationError(DomainError):
    error_code = ErrorCode.ASSET_INVALID
    retryable = False


class AssetNotFound(DomainError):
    error_code = ErrorCode.ASSET_NOT_FOUND
    retryable = False


class AssetAccessDenied(DomainError):
    error_code = ErrorCode.FORBIDDEN
    retryable = False


def _detect_mime(data: bytes) -> str | None:
    for mime, sig in _SIGNATURES.items():
        if mime == "image/webp":
            if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                return mime
        elif data.startswith(sig):
            return mime
    return None


def _safe_prefix(value: str) -> str:
    """스토리지 key prefix 정규화. 절대경로·상위경로는 저장소 종류와 무관하게 거부한다."""
    raw = value.replace("\\", "/").strip("/")
    if not raw:
        return _DEFAULT_VIDEO_PREFIX
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("잘못된 Studio 출력 prefix")
    return path.as_posix()


class AssetService:
    def __init__(
        self,
        store: AssetStore,
        repo: AssetRepository,
        generated_video_prefix: str = _DEFAULT_VIDEO_PREFIX,
        generated_video_expiry_days: int = 7,
    ) -> None:
        self._store = store
        self._repo = repo
        self._generated_video_prefix = _safe_prefix(generated_video_prefix)
        self._generated_video_expiry = timedelta(days=max(1, generated_video_expiry_days))

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

    def register_generated_video(
        self,
        data: bytes,
        owner_id: str | None = None,
        consultation_id: str | None = None,
        mime_type: str = "video/mp4",
    ) -> Asset:
        """생성된 영상 바이트를 설정된 prefix 아래 저장하고 GENERATED_VIDEO 메타데이터를 기록한다."""
        if not data:
            raise AssetValidationError("빈 결과 파일")
        if mime_type == "video/mp4" and not is_probable_mp4(data):
            raise AssetValidationError("지원하지 않는 영상 형식")
        asset_id = str(uuid.uuid4())
        storage_key = f"{self._generated_video_prefix}/{asset_id}.mp4"
        self._store.save(storage_key, data, mime_type)
        asset = Asset(
            id=asset_id,
            owner_type="SALON_MEMBER" if owner_id else "SYSTEM",
            asset_type="GENERATED_VIDEO",
            storage_key=storage_key,
            mime_type=mime_type,
            byte_size=len(data),
            owner_id=owner_id,
            consultation_id=consultation_id,
            sha256=hashlib.sha256(data).hexdigest(),
            expires_at=_utcnow() + self._generated_video_expiry,
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

    def get_bytes_for_user(self, asset_id: str, user_id: str | None) -> tuple[bytes, str] | None:
        """권한 확인 후 다운로드용 바이트를 반환한다.

        스캐폴드의 선택적 인증 상태에서도 고객 얼굴/결과 바이트가 asset_id 만으로 노출되지 않게
        최소 소유자 확인을 적용한다. owner_id 가 없는 익명 에셋은 공개 다운로드하지 않는다.
        """
        asset = self._repo.get(asset_id)
        if asset is None or asset.status != "ACTIVE":
            return None
        if user_id is None or asset.owner_id is None or asset.owner_id != user_id:
            raise AssetAccessDenied()
        try:
            return self._store.load(asset.storage_key), asset.mime_type
        except FileNotFoundError:
            return None

    def assert_reference_allowed(
        self,
        asset_id: str,
        user_id: str | None,
        allowed_types: set[str],
    ) -> Asset:
        """Studio 입력에서 참조하는 asset_id 의 존재·상태·소유자·타입을 확인한다.

        바이트와 storage_key 는 반환하지 않고, 서비스 내부 메타데이터만 확인한다.
        """
        try:
            asset = self._repo.get(asset_id)
        except ValueError as exc:
            raise AssetValidationError("잘못된 asset_id") from exc
        if asset is None or asset.status != "ACTIVE":
            raise AssetNotFound()
        if asset.asset_type not in allowed_types:
            raise AssetValidationError("지원하지 않는 asset_type")
        if asset.owner_id is not None and asset.owner_id != user_id:
            raise AssetAccessDenied()
        return asset

    def load_reference_bytes(
        self,
        asset_id: str,
        user_id: str | None,
        allowed_types: set[str],
    ) -> tuple[bytes, str]:
        """Provider 내부 입력용 바이트 조회.

        반환값은 API 응답이나 로그로 내보내지 않고, backend-owned provider 호출에만 사용한다.
        """
        asset = self.assert_reference_allowed(asset_id, user_id, allowed_types)
        try:
            return self._store.load(asset.storage_key), asset.mime_type
        except FileNotFoundError as exc:
            raise AssetNotFound() from exc
