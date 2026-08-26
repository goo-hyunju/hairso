"""로컬 헤어 리스타일 추론 서비스 — BE(apimgr)가 HTTP로 호출하는 '로컬 모델 서비스'.

무거운 ML 스택(torch/diffusers/모델)을 API 서버와 분리하기 위한 별도 프로세스(§4.9 Worker 분리 원칙).
모델은 기동 시 1회 로드(요청마다 재로드 금지). 얼굴 이미지 바이트는 응답으로만 오가고 디스크·로그에 남기지 않는다(§4.13/§0.15).

기동:  ml/.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188
엔드포인트:
  GET  /health              → {"status":"ok","device":...}
  POST /restyle (multipart) → image=<파일>, prompt=<str>, [negative_prompt, steps, seed] → PNG 바이트
  POST /video/i2v           → image? + prompt → LOCAL_VIDEO_RENDER_COMMAND 로 생성한 MP4 바이트
"""

from __future__ import annotations

import io
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

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


def _is_probable_mp4(data: bytes) -> bool:
    return len(data) >= 12 and b"ftyp" in data[:32]


@app.post("/video/i2v")
async def video_i2v(
    image: UploadFile | None = File(None),
    prompt: str = Form(...),
    duration_seconds: int = Form(5),
    aspect_ratio: str = Form("9:16"),
    quality: str = Form("720p"),
    idempotency_key: str = Form(...),
    model: str | None = Form(None),
    negative_prompt: str | None = Form(None),
    seed: int | None = Form(None),
) -> Response:
    """Wan/CogVideoX/ComfyUI 등 로컬 렌더 명령을 감싼 MP4 생성 엔드포인트.

    모델 실행 명령은 `LOCAL_VIDEO_RENDER_COMMAND` 로 명시 설정한다. 예:
    `python wan_i2v.py --image {input} --prompt-file {prompt_file} --output {output}`
    """
    command_template = os.environ.get("LOCAL_VIDEO_RENDER_COMMAND", "").strip()
    if not command_template:
        raise HTTPException(status_code=503, detail="LOCAL_VIDEO_RENDER_COMMAND_NOT_CONFIGURED")

    with tempfile.TemporaryDirectory(prefix="hairso-video-") as tmp:
        tmpdir = Path(tmp)
        input_path = tmpdir / "source"
        output_path = tmpdir / "output.mp4"
        prompt_path = tmpdir / "prompt.txt"
        meta_path = tmpdir / "request.env"

        if image is not None:
            input_path.write_bytes(await image.read())
        prompt_path.write_text(prompt, encoding="utf-8")
        meta_path.write_text(
            "\n".join(
                [
                    f"duration_seconds={duration_seconds}",
                    f"aspect_ratio={aspect_ratio}",
                    f"quality={quality}",
                    f"idempotency_key={idempotency_key}",
                    f"model={model or ''}",
                    f"negative_prompt={negative_prompt or ''}",
                    f"seed={seed if seed is not None else ''}",
                ]
            ),
            encoding="utf-8",
        )

        args = [
            part.format(
                input=str(input_path) if image is not None else "",
                output=str(output_path),
                prompt_file=str(prompt_path),
                meta_file=str(meta_path),
            )
            for part in shlex.split(command_template)
        ]
        try:
            completed = subprocess.run(
                args,
                check=False,
                cwd=str(tmpdir),
                capture_output=True,
                timeout=int(os.environ.get("LOCAL_VIDEO_RENDER_TIMEOUT_SECONDS", "900")),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=502, detail="LOCAL_VIDEO_RENDER_FAILED") from exc

        if completed.returncode != 0 or not output_path.is_file():
            raise HTTPException(status_code=502, detail="LOCAL_VIDEO_RENDER_FAILED")
        data = output_path.read_bytes()
        if not _is_probable_mp4(data):
            raise HTTPException(status_code=502, detail="LOCAL_VIDEO_RENDER_INVALID_MP4")
        return Response(content=data, media_type="video/mp4")
