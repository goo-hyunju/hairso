"""테스트용 가상 얼굴 생성 — 실존 인물/데이터셋 얼굴을 쓰지 않기 위해(§4.13) 직접 생성한다.

이미 캐시된 SD1.5-inpainting 모델에 '전체 흰 마스크'를 주면 txt2img 처럼 동작한다(추가 다운로드 0).
결과는 존재하지 않는 사람의 정면 초상 → face-parsing/헤어 리스타일 파이프라인 테스트 픽스처.
"""

from __future__ import annotations

import os

import torch
from diffusers import AutoPipelineForInpainting
from PIL import Image

MODEL_ID = os.environ.get("INPAINT_MODEL", "stable-diffusion-v1-5/stable-diffusion-inpainting")
OUT = os.path.join(os.path.dirname(__file__), "test_face.jpg")
SIZE = 512

pipe = AutoPipelineForInpainting.from_pretrained(MODEL_ID, torch_dtype=torch.float16).to("cuda")
pipe.enable_attention_slicing()

base = Image.new("RGB", (SIZE, SIZE), (127, 127, 127))
full_mask = Image.new("L", (SIZE, SIZE), 255)  # 전체 생성
gen = torch.Generator("cuda").manual_seed(7)
img = pipe(
    prompt=(
        "a color studio portrait photograph of a young east asian woman, "
        "long straight black hair, plain light gray background, front view, "
        "looking at camera, neutral expression, sharp focus, natural skin"
    ),
    negative_prompt="blurry, deformed, cartoon, painting, multiple people",
    image=base,
    mask_image=full_mask,
    num_inference_steps=30,
    guidance_scale=8.0,
    generator=gen,
).images[0]
img.save(OUT)
print(f"saved {OUT} ({img.size})")
