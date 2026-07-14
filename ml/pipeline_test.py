"""2단계 — 자동 마스킹 헤어 리스타일 파이프라인 end-to-end 검증(실제 얼굴 픽스처).

test_face.jpg 에 여러 헤어스타일 프롬프트를 적용 → outputs/restyle_*.png 저장.
검증: (1) face-parsing 마스크가 실제 머리만 잡는지 (2) 얼굴/배경 원본 보존 (3) 스타일별로 머리만 바뀌는지.
"""

from __future__ import annotations

import os
import time

import numpy as np
from PIL import Image

from restyle import HairRestyler

OUT = os.path.join(os.path.dirname(__file__), "outputs")
SRC = os.path.join(os.path.dirname(__file__), "test_face.jpg")

STYLES = {
    "bob": "short jaw-length bob haircut, blunt cut, straight, dark brown hair, salon photo",
    "wavy_short": "short wavy bob, soft inward c-curl, layered, light brown hair, salon photo",
    "bangs": "medium length hair with full see-through bangs, straight black hair, salon photo",
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    base = Image.open(SRC).convert("RGB").resize((512, 512))

    t0 = time.time()
    restyler = HairRestyler()
    print(f"모델 로드 {time.time() - t0:.1f}s (2개 모델: inpaint + face-parsing)")

    base.save(os.path.join(OUT, "restyle_before.png"))
    base_arr = np.asarray(base)

    for name, prompt in STYLES.items():
        t = time.time()
        result, mask = restyler.restyle(base, prompt, seed=42)
        dt = time.time() - t

        # 얼굴 보존 검증: 마스크가 완전히 0인 영역은 원본과 픽셀 동일해야 한다.
        hard_keep = np.asarray(mask) == 0
        same = np.array_equal(np.asarray(result)[hard_keep], base_arr[hard_keep])
        coverage = np.asarray(mask).mean() / 255.0

        result.save(os.path.join(OUT, f"restyle_{name}.png"))
        mask.save(os.path.join(OUT, f"restyle_{name}_mask.png"))
        print(f"[{name}] {dt:.1f}s | 머리비율 {coverage:.1%} | 마스크밖 원본동일 {same}")

    print(f"저장: {OUT}/restyle_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
