"""Asset 저장소 인터페이스 + 인메모리 구현(메타데이터 — 바이트는 AssetStore 담당).

generation_repository 와 동일 값 의미론: save 는 복사본 보관, get 은 복사본 반환(참조 공유로 인한
false green 방지). 실 DB 구현은 supabase_asset_repository.SupabaseAssetRepository.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod

from app.domain.models import Asset


class AssetRepository(ABC):
    @abstractmethod
    def save(self, asset: Asset) -> Asset:
        ...

    @abstractmethod
    def get(self, asset_id: str) -> Asset | None:
        ...


class InMemoryAssetRepository(AssetRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, Asset] = {}

    def save(self, asset: Asset) -> Asset:
        self._by_id[asset.id] = copy.copy(asset)
        return asset

    def get(self, asset_id: str) -> Asset | None:
        a = self._by_id.get(asset_id)
        return copy.copy(a) if a is not None else None
