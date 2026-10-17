"""헤어 리스타일 핵심 로직 — 얼굴 유지 + 머리만 변경(§6.1). BE LocalImageProvider 가 호출할 재사용 모듈.

흐름: 입력 얼굴 → face-parsing 헤어 마스크 → SD inpainting(머리만) → 마스크 밖 원본 강제 합성 → 결과.
파이프라인/모델은 인스턴스당 1회 로드(무거운 로드를 요청마다 반복하지 않음).
"""

from __future__ import annotations

import os

import numpy as np
import torch
from diffusers import AutoPipelineForInpainting
from PIL import Image

import hair_mask as hair_mask_mod
from hair_mask import hair_mask

INPAINT_MODEL = os.environ.get("INPAINT_MODEL", "stable-diffusion-v1-5/stable-diffusion-inpainting")
SIZE = 512
# 얼굴 정체성 보존을 돕는 기본 네거티브(§6.1) — 얼굴 변형/다른 사람화 억제.
_DEFAULT_NEG = "different person, distorted face, deformed, disfigured, blurry, extra head, cartoon"


class HairRestyler:
    def __init__(self, model_id: str = INPAINT_MODEL) -> None:
        self._pipe = AutoPipelineForInpainting.from_pretrained(model_id, torch_dtype=torch.float16)
        self._pipe = self._pipe.to("cuda" if torch.cuda.is_available() else "cpu")
        self._pipe.enable_attention_slicing()  # 8GB VRAM 여유
        self._pipe.set_progress_bar_config(disable=True)

    def to_device(self, device: str) -> None:
        """inpaint 파이프라인과 face-parsing 모델을 함께 이동 — 영상 생성과 8GB VRAM 을 나눠 쓰기 위한 스왑."""
        self._pipe = self._pipe.to(device)
        hair_mask_mod.set_device(device)

    def restyle(
        self,
        image: Image.Image,
        prompt: str,
        negative_prompt: str | None = None,
        steps: int = 30,
        guidance_scale: float = 7.5,
        seed: int | None = None,
    ) -> tuple[Image.Image, Image.Image]:
        """입력 얼굴에 새 헤어스타일을 적용해 (결과이미지, 사용한마스크) 반환."""
        image = image.convert("RGB").resize((SIZE, SIZE))
        mask = hair_mask(image)

        gen = None
        if seed is not None:
            gen = torch.Generator(self._pipe.device.type).manual_seed(seed)
        out = self._pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or _DEFAULT_NEG,
            image=image,
            mask_image=mask,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=gen,
        ).images[0].resize((SIZE, SIZE))

        # 마스크 밖 픽셀은 원본으로 강제 합성 → 얼굴/배경 보존 보장(흰=생성, 검정=원본).
        m = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
        composite = (np.asarray(out) * m + np.asarray(image) * (1 - m)).astype(np.uint8)
        return Image.fromarray(composite), mask
