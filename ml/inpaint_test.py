"""1단계 PoC — 로컬 inpainting 파이프라인이 이 GPU(8GB)에서 실제로 도는지 + '마스크 영역만 변경'을 검증.

핵심 설계(§6.1 얼굴 유지): inpainting 출력에서 **마스크 밖 픽셀은 원본으로 강제 합성**한다.
→ 얼굴/배경은 픽셀 단위로 원본과 동일함이 보장되고, 마스크(머리 영역)만 새로 생성된다.

사용:
  python inpaint_test.py --image path/to/face.jpg          # 실제 사진(권장)
  python inpaint_test.py                                    # 입력 없으면 합성 테스트 이미지로 파이프라인만 증명

출력: outputs/ 에 before/after/mask 저장. 콘솔에 VRAM 피크와 '마스크 밖 동일' 검증 결과.
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
import torch
from diffusers import AutoPipelineForInpainting
from PIL import Image, ImageDraw, ImageFilter

# SD1.5 inpainting 공식 재호스팅본(runway 삭제 후 커뮤니티 유지). 공개·비게이팅, 8GB fp16 에 여유.
# stabilityai/SD2-inpainting 은 게이팅(401)이라 회피. 품질 필요 시 SDXL inpainting
# ("diffusers/stable-diffusion-xl-1.0-inpainting-0.1")로 교체(같은 인터페이스, VRAM 더 씀).
MODEL_ID = os.environ.get("INPAINT_MODEL", "stable-diffusion-v1-5/stable-diffusion-inpainting")
OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
SIZE = 512


def _synthetic_face(size: int = SIZE) -> Image.Image:
    """입력 사진이 없을 때 파이프라인만 증명하기 위한 합성 이미지(초록 배경 + 살색 얼굴 타원)."""
    img = Image.new("RGB", (size, size), (60, 140, 90))
    d = ImageDraw.Draw(img)
    d.ellipse([size * 0.28, size * 0.30, size * 0.72, size * 0.85], fill=(226, 190, 160))  # 얼굴
    d.ellipse([size * 0.40, size * 0.48, size * 0.46, size * 0.54], fill=(40, 40, 40))     # 눈
    d.ellipse([size * 0.54, size * 0.48, size * 0.60, size * 0.54], fill=(40, 40, 40))
    return img


def _hair_mask(size: int = SIZE) -> Image.Image:
    """머리 영역 근사 마스크(상단 반원 밴드). 흰색=생성, 검정=보존.
    실서비스는 face-parsing 세그멘테이션으로 정밀 마스크를 만든다(다음 단계)."""
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([size * 0.18, size * 0.02, size * 0.82, size * 0.55], fill=255)  # 이마 위 머리 밴드
    d.rectangle([0, 0, size, size * 0.10], fill=255)
    return m.filter(ImageFilter.GaussianBlur(6))  # 경계 부드럽게


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="입력 얼굴 사진(없으면 합성)")
    ap.add_argument("--prompt", default="short jaw-length bob haircut, soft inward c-curl, dark brown hair")
    ap.add_argument("--steps", type=int, default=25)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.image:
        base = Image.open(args.image).convert("RGB").resize((SIZE, SIZE))
    else:
        base = _synthetic_face()
        print("입력 이미지 없음 → 합성 테스트 이미지 사용(파이프라인 증명용)")
    mask = _hair_mask()

    print(f"모델 로드: {MODEL_ID} (최초 실행은 다운로드 발생)")
    t0 = time.time()
    pipe = AutoPipelineForInpainting.from_pretrained(MODEL_ID, torch_dtype=torch.float16)
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()  # 8GB VRAM 여유 확보
    torch.cuda.reset_peak_memory_stats()
    print(f"로드 완료 {time.time() - t0:.1f}s")

    t1 = time.time()
    gen = torch.Generator("cuda").manual_seed(42)
    out = pipe(
        prompt=args.prompt,
        image=base,
        mask_image=mask,
        num_inference_steps=args.steps,
        guidance_scale=7.5,
        generator=gen,
    ).images[0].resize((SIZE, SIZE))
    torch.cuda.synchronize()
    peak = torch.cuda.max_memory_allocated() / 1e9
    print(f"생성 완료 {time.time() - t1:.1f}s / VRAM peak {peak:.2f}GB")

    # 마스크 밖 픽셀을 원본으로 강제 합성(얼굴 보존 보장) — 흰(255)=생성, 검정(0)=원본.
    m = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
    composite = (np.asarray(out) * m + np.asarray(base) * (1 - m)).astype(np.uint8)
    comp_img = Image.fromarray(composite)

    # 검증: 마스크가 완전히 0인 영역(하드 보존부)은 원본과 픽셀 동일해야 한다.
    hard_keep = (np.asarray(mask) == 0)
    same = np.array_equal(composite[hard_keep], np.asarray(base)[hard_keep])
    print(f"마스크 밖(하드 보존) 원본과 동일: {same}")

    base.save(os.path.join(OUT_DIR, "before.png"))
    mask.save(os.path.join(OUT_DIR, "mask.png"))
    out.save(os.path.join(OUT_DIR, "raw_output.png"))
    comp_img.save(os.path.join(OUT_DIR, "after.png"))
    print(f"저장: {OUT_DIR} (before/mask/raw_output/after.png)")
    print("PASS" if same else "WARN: 하드 보존부 불일치 — 합성 로직 확인 필요")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
