"""로컬 디스크 에셋 저장소 — 자격증명 없이 즉시 동작. Supabase Storage 준비 전 개발용 기본값.

고객 얼굴/결과가 저장되므로 루트는 repo 밖 경로를 쓴다(§4.13). 키에 상위경로(..)·절대경로를 막아
루트 밖 쓰기(경로 이탈)를 차단한다. 원본 얼굴 바이트는 로그에 남기지 않는다(§0.15).
"""

from __future__ import annotations

from pathlib import Path

from app.providers.storage.base import AssetStore


class LocalDiskAssetStore(AssetStore):
    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # key 는 상대 경로여야 하며, 최종 경로가 루트 밖이면 거부(경로 이탈 방지).
        target = (self._root / key).resolve()
        if self._root not in target.parents and target != self._root:
            raise ValueError("잘못된 저장 키(루트 밖 경로)")
        return target

    def save(self, key: str, data: bytes, content_type: str) -> None:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def load(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()
