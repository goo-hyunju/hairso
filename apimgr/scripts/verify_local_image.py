"""(1) 로컬 이미지 생성 end-to-end 검증 — DB·계약 미변경, 자격증명 불필요.

경로: 얼굴 바이트를 LocalDiskAssetStore 에 저장 → LocalImageProvider.submit → ml 추론 서비스 호출
      → 결과를 서버와 같은 에셋 루트(ASSET_LOCAL_ROOT, 미설정 시 config 기본값)에 저장 → get_status SUCCEEDED → 결과 PNG 확인.

전제: ml/serve.py 추론 서비스가 LOCAL_INFERENCE_URL(기본 127.0.0.1:8188)에서 실행 중.
실행: apimgr 디렉터리에서  .venv/Scripts/python scripts/verify_local_image.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

# apimgr 루트를 import 경로에 추가(스크립트 단독 실행 대비).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.providers.image_generation.base import ImageGenerationInput, ImageVariant
from app.providers.image_generation.local import LocalImageProvider
from app.providers.storage.local_disk import LocalDiskAssetStore

ASSET_ROOT = get_settings().asset_local_root
INFER_URL = os.environ.get("LOCAL_INFERENCE_URL", "http://127.0.0.1:8188")
FACE_SRC = Path(__file__).resolve().parent.parent.parent / "ml" / "test_face.jpg"


async def main() -> int:
    store = LocalDiskAssetStore(ASSET_ROOT)
    provider = LocalImageProvider(store, INFER_URL)

    # 1) 얼굴 에셋을 저장소에 넣는다(업로드 시뮬레이션 — 정식 업로드 엔드포인트는 (2)).
    face_asset_id = str(uuid.uuid4())
    store.save(LocalImageProvider.face_key(face_asset_id), FACE_SRC.read_bytes(), "image/png")
    print(f"face 저장: {LocalImageProvider.face_key(face_asset_id)} (root={ASSET_ROOT})")

    # 2) 생성 요청(§6.1 얼굴 유지 + 머리만 변경).
    data = ImageGenerationInput(
        face_asset_id=face_asset_id,
        style_reference_asset_id=None,
        style_structure={"length": "jaw_length_bob", "curl": "soft_inward_c_curl", "color": "dark_brown"},
        variant=ImageVariant.SIMILAR,
        prompt="short jaw-length bob haircut, soft inward c-curl, dark brown hair, salon photo",
        idempotency_key=f"verify-{face_asset_id[:8]}",
    )

    sub = await provider.submit(data)
    print(f"submit → provider={sub.provider.value} job={sub.external_job_id} cost={sub.estimated_cost_usd}")

    status = await provider.get_status(sub.external_job_id)
    print(f"status → {status.status.value} output_key={status.output_url}")

    # 3) 결과가 실제로 저장됐는지 + PNG 인지 확인.
    ok = status.output_url is not None and store.exists(status.output_url)
    is_png = False
    saved_path = None
    if ok:
        data_out = store.load(status.output_url)
        is_png = data_out[:8] == b"\x89PNG\r\n\x1a\n"
        saved_path = Path(ASSET_ROOT) / status.output_url
    print(f"결과 저장 확인: {ok} | PNG 유효: {is_png}")
    print(f"저장 위치: {saved_path}")
    print("PASS" if (ok and is_png) else "FAIL")
    return 0 if (ok and is_png) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
