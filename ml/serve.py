"""로컬 헤어 리스타일 추론 서비스 — BE(apimgr)가 HTTP로 호출하는 '로컬 모델 서비스'.

무거운 ML 스택(torch/diffusers/모델)을 API 서버와 분리하기 위한 별도 프로세스(§4.9 Worker 분리 원칙).
모델은 기동 시 1회 로드(요청마다 재로드 금지). 얼굴 이미지 바이트는 응답으로만 오가고 디스크·로그에 남기지 않는다(§4.13/§0.15).

기동:  ml/.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188
엔드포인트:
  GET  /health              → {"status":"ok","device":...}
  POST /restyle (multipart) → image=<파일>, prompt=<str>, [negative_prompt, steps, seed] → PNG 바이트
"""

from __future__ import annotations

import io

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from restyle import HairRestyler

app = FastAPI(title="hairso local inference", version="0.1.0")
_restyler: HairRestyler | None = None


def _get_restyler() -> HairRestyler:
    global _restyler
    if _restyler is None:
        _restyler = HairRestyler()  # 최초 요청 시 1회 로드(inpaint + face-parsing)
    return _restyler


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "device": "cuda" if torch.cuda.is_available() else "cpu"}


@app.post("/restyle")
async def restyle(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str | None = Form(None),
    steps: int = Form(30),
    seed: int | None = Form(None),
) -> Response:
    """얼굴 이미지 + 헤어 프롬프트 → 얼굴 유지·머리만 변경한 PNG. (얼굴 정체성 보존은 restyle 내부 합성이 보장)"""
    raw = await image.read()
    try:
        src = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="ASSET_INVALID")  # 디코드 불가

    result, _mask = _get_restyler().restyle(
        src, prompt=prompt, negative_prompt=negative_prompt, steps=steps, seed=seed
    )
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
