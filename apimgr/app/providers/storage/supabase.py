"""Supabase Storage 에셋 저장소 — 서버측 업로드/다운로드(비공개 버킷 hairview-assets).

Storage REST API + secret 키(sb_secret_... = service_role 역할)로 접근. secret 키는 로그에 남기지 않는다(§0.14).
비공개 버킷이므로 공개 URL 을 저장하지 않고(§4.13), 필요 시 짧은 만료의 signed URL 을 발급한다.

AssetStore 인터페이스(동기)를 httpx.Client(동기)로 구현 — LocalDiskAssetStore 와 교체 가능.
"""

from __future__ import annotations

import httpx

from app.providers.storage.base import AssetStore


class SupabaseAssetStore(AssetStore):
    def __init__(self, supabase_url: str, secret_key: str, bucket: str, timeout_s: float = 30.0) -> None:
        self._base = supabase_url.rstrip("/")
        self._secret = secret_key  # 로그 출력 금지
        self._bucket = bucket
        self._timeout = timeout_s

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._secret}", "apikey": self._secret}
        if extra:
            h.update(extra)
        return h

    def _object_url(self, key: str) -> str:
        return f"{self._base}/storage/v1/object/{self._bucket}/{key}"

    def save(self, key: str, data: bytes, content_type: str) -> None:
        # x-upsert: 같은 키 재업로드 허용(멱등 재시도 안전).
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                self._object_url(key),
                content=data,
                headers=self._headers({"Content-Type": content_type, "x-upsert": "true"}),
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Supabase Storage 업로드 실패 status={resp.status_code}")

    def load(self, key: str) -> bytes:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(self._object_url(key), headers=self._headers())
        if resp.status_code == 404:
            raise FileNotFoundError(key)
        if resp.status_code != 200:
            raise RuntimeError(f"Supabase Storage 다운로드 실패 status={resp.status_code}")
        return resp.content

    def exists(self, key: str) -> bool:
        # HEAD(info) 로 존재만 확인 — 바이트를 받지 않는다.
        info_url = f"{self._base}/storage/v1/object/info/{self._bucket}/{key}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(info_url, headers=self._headers())
        return resp.status_code == 200

    def create_signed_url(self, key: str, expires_in_s: int = 3600) -> str:
        """비공개 버킷의 임시 접근용 signed URL(§4.13 — 영구 공개 URL 저장 금지)."""
        url = f"{self._base}/storage/v1/object/sign/{self._bucket}/{key}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json={"expiresIn": expires_in_s}, headers=self._headers())
        if resp.status_code != 200:
            raise RuntimeError(f"signed URL 발급 실패 status={resp.status_code}")
        signed = resp.json().get("signedURL", "")
        return f"{self._base}/storage/v1{signed}"
