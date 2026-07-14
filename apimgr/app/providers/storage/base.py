"""에셋 바이트 저장소 공통 인터페이스 — 로컬 디스크(지금) ↔ Supabase Storage(로드맵) 교체 지점.

Service/Provider 는 이 인터페이스에만 의존한다. 백엔드 교체 시 호출부 무변경(§4.6 Provider 패턴).
바이트의 '메타데이터'(mime/size/owner/만료)는 assets 테이블(AssetRepository)이, '바이트 자체'는 이 저장소가 담당.

키(key) 규약: "<asset_type_dir>/<uuid>.<ext>" 형태의 상대 경로. 절대경로·상위경로(..) 금지(경로 이탈 방지).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AssetStore(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> None:
        """key 위치에 바이트 저장(있으면 덮어씀). content_type 은 백엔드가 필요 시 사용."""

    @abstractmethod
    def load(self, key: str) -> bytes:
        """key 의 바이트를 읽는다. 없으면 FileNotFoundError."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...
