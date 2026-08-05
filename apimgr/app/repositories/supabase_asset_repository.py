"""Asset 저장소의 Supabase(psycopg 동기) 구현 — assets 테이블(§4.13 메타데이터만).

원본/공개 URL 은 저장하지 않는다(storage_key·mime·size·hash·만료만). generation repo 와 동일하게
메서드마다 새 연결을 연다(스캐폴드 단순화; 부하 시 psycopg_pool 로 교체).
"""

from __future__ import annotations

import uuid

import psycopg
from psycopg.rows import dict_row

from app.domain.models import Asset
from app.repositories.asset_repository import AssetRepository

_COLUMNS = (
    "id, owner_type, owner_id, consultation_id, asset_type, storage_key, mime_type, "
    "byte_size, width, height, sha256, status, expires_at, deleted_at, created_at"
)


def _uid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _row_to_asset(row: dict) -> Asset:
    return Asset(
        id=str(row["id"]),
        owner_type=row["owner_type"],
        asset_type=row["asset_type"],
        storage_key=row["storage_key"],
        mime_type=row["mime_type"],
        byte_size=row["byte_size"],
        owner_id=str(row["owner_id"]) if row["owner_id"] is not None else None,
        consultation_id=str(row["consultation_id"]) if row["consultation_id"] is not None else None,
        width=row["width"],
        height=row["height"],
        sha256=row["sha256"],
        status=row["status"],
        expires_at=row["expires_at"],
        deleted_at=row["deleted_at"],
        created_at=row["created_at"],
    )


class SupabaseAssetRepository(AssetRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def save(self, asset: Asset) -> Asset:
        params = {
            "id": _uid(asset.id),
            "owner_type": asset.owner_type,
            "owner_id": _uid(asset.owner_id),
            "consultation_id": _uid(asset.consultation_id),
            "asset_type": asset.asset_type,
            "storage_key": asset.storage_key,
            "mime_type": asset.mime_type,
            "byte_size": asset.byte_size,
            "width": asset.width,
            "height": asset.height,
            "sha256": asset.sha256,
            "status": asset.status,
            "expires_at": asset.expires_at,
            "deleted_at": asset.deleted_at,
            "created_at": asset.created_at,
        }
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            conn.execute(
                """
                INSERT INTO public.assets
                    (id, owner_type, owner_id, consultation_id, asset_type, storage_key,
                     mime_type, byte_size, width, height, sha256, status, expires_at,
                     deleted_at, created_at)
                VALUES
                    (%(id)s, %(owner_type)s, %(owner_id)s, %(consultation_id)s, %(asset_type)s,
                     %(storage_key)s, %(mime_type)s, %(byte_size)s, %(width)s, %(height)s,
                     %(sha256)s, %(status)s, %(expires_at)s, %(deleted_at)s, %(created_at)s)
                """,
                params,
            )
        return asset

    def get(self, asset_id: str) -> Asset | None:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM public.assets WHERE id=%s", (_uid(asset_id),)
            ).fetchone()
        return _row_to_asset(row) if row is not None else None
