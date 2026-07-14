"""face-parsing 기반 헤어 마스크 생성 — '머리 영역만' 정밀 분할(§6.1 얼굴 보존의 핵심).

jonathandinu/face-parsing (SegFormer, CelebAMask-HQ 19클래스)로 픽셀 단위 분할 후 'hair' 클래스만 추출.
조잡한 타원 마스크 대신 실제 머리 픽셀만 잡으므로, 마스크 밖(얼굴/피부/배경)은 원본 그대로 보존된다.

반환: L 모드 마스크(흰=재생성(머리), 검정=보존). dilate 로 새 헤어가 확장될 여지를 주고 feather 로 경계 완화.
"""

from __future__ import annotations

import numpy as np
import torch
from PIL import Image, ImageFilter
from transformers import AutoModelForSemanticSegmentation

_MODEL_ID = "jonathandinu/face-parsing"
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_model: AutoModelForSemanticSegmentation | None = None

# SegFormer 표준 전처리 상수(ImageNet). 저장소 preprocessor_config 가 구형식이라 AutoImageProcessor
# 자동추론이 실패 → 전처리를 직접 구현해 transformers 버전 변화에 무관하게 동작시킨다.
_SEG_SIZE = 512
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _load() -> AutoModelForSemanticSegmentation:
    global _model
    if _model is None:
        _model = AutoModelForSemanticSegmentation.from_pretrained(_MODEL_ID).to(_DEVICE)
        _model.eval()
    return _model


def _hair_class_id(model: AutoModelForSemanticSegmentation) -> int:
    """config.id2label 에서 'hair' 클래스 id 를 찾는다(순서 하드코딩 회피)."""
    for idx, label in model.config.id2label.items():
        if str(label).lower() == "hair":
            return int(idx)
    raise RuntimeError("face-parsing 모델에 'hair' 클래스가 없습니다")


def _preprocess(image: Image.Image) -> torch.Tensor:
    """PIL → SegFormer 입력 텐서(1,3,H,W): resize→[0,1]→ImageNet 정규화."""
    im = image.convert("RGB").resize((_SEG_SIZE, _SEG_SIZE))
    arr = (np.asarray(im, dtype=np.float32) / 255.0 - _MEAN) / _STD  # HWC
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).contiguous()


def parse_labels(image: Image.Image) -> np.ndarray:
    """이미지를 픽셀 단위 클래스 라벨 맵(원본 H, W)으로 분할."""
    model = _load()
    pixel_values = _preprocess(image).to(_DEVICE)
    with torch.no_grad():
        logits = model(pixel_values=pixel_values).logits  # (1, C, h, w)
    up = torch.nn.functional.interpolate(
        logits, size=(image.height, image.width), mode="bilinear", align_corners=False
    )
    return up.argmax(dim=1)[0].to("cpu").numpy()


def hair_mask(image: Image.Image, dilate_px: int = 18, feather_px: int = 6) -> Image.Image:
    """머리 영역 마스크(L). dilate_px 로 새 헤어 확장 여지(길이 변화 대응), feather_px 로 경계 완화.

    dilate 는 scipy 없이 GaussianBlur+threshold 로 근사한다(블러로 번진 뒤 낮은 임계값으로 이진화 = 팽창).
    """
    model = _load()
    labels = parse_labels(image)
    hair_id = _hair_class_id(model)
    raw = (labels == hair_id).astype(np.uint8) * 255
    m = Image.fromarray(raw, mode="L")

    if dilate_px > 0:
        blurred = np.asarray(m.filter(ImageFilter.GaussianBlur(dilate_px)))
        grown = (blurred > 25).astype(np.uint8) * 255  # 임계값 낮춰 영역 팽창
        m = Image.fromarray(grown, mode="L")
    if feather_px > 0:
        m = m.filter(ImageFilter.GaussianBlur(feather_px))
    return m


if __name__ == "__main__":
    import os
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "test_face.jpg")
    img = Image.open(src).convert("RGB")
    mask = hair_mask(img)
    out_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    mask.save(os.path.join(out_dir, "hair_mask.png"))
    coverage = np.asarray(mask).mean() / 255.0
    print(f"hair mask 저장. 머리 영역 비율(대략): {coverage:.1%}")
