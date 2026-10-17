"""로컬 헤어 리스타일 추론 서비스 — BE(apimgr)가 HTTP로 호출하는 '로컬 모델 서비스'.

무거운 ML 스택(torch/diffusers/모델)을 API 서버와 분리하기 위한 별도 프로세스(§4.9 Worker 분리 원칙).
모델은 기동 시 1회 로드(요청마다 재로드 금지). 얼굴 이미지 바이트는 응답으로만 오가고 디스크·로그에 남기지 않는다(§4.13/§0.15).

기동:  ml/.venv/Scripts/python -m uvicorn serve:app --host 127.0.0.1 --port 8188
엔드포인트:
  GET  /health              → {"status":"ok","device":...}
  POST /restyle (multipart) → image=<파일>, prompt=<str>, [negative_prompt, steps, seed] → PNG 바이트
  POST /video/i2v           → image? + prompt → job_id 즉시 반환
  GET  /video/i2v/{job_id}  → 로컬 영상 생성 상태 조회
  GET  /video/i2v/{job_id}/output → 완료된 MP4 바이트
"""

from __future__ import annotations

import asyncio
import io
import os
import shlex
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, UnidentifiedImageError

from restyle import HairRestyler
from wan_video import WanVideoGenerationError, WanVideoGenerator

app = FastAPI(title="hairso local inference", version="0.1.0")
_restyler: HairRestyler | None = None
_wan_video_generator: WanVideoGenerator | None = None
_gpu_lock = asyncio.Lock()


@dataclass(frozen=True, repr=False)
class VideoRenderRequest:
    image_bytes: bytes | None
    prompt: str
    duration_seconds: int
    aspect_ratio: str
    quality: str
    idempotency_key: str
    model: str | None
    negative_prompt: str | None
    seed: int | None


@dataclass
class VideoJob:
    job_id: str
    status: str = "PENDING"
    video_bytes: bytes | None = None
    error_code: str | None = None


_video_jobs: dict[str, VideoJob] = {}
_video_job_by_idempotency_key: dict[str, str] = {}


def _get_restyler() -> HairRestyler:
    global _restyler
    if _restyler is None:
        _restyler = HairRestyler()  # 최초 요청 시 1회 로드(inpaint + face-parsing)
    return _restyler


def _get_wan_video_generator() -> WanVideoGenerator:
    global _wan_video_generator
    if _wan_video_generator is None:
        _wan_video_generator = WanVideoGenerator()
    return _wan_video_generator


_ACCEL_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def _release_gpu_for_video() -> None:
    """영상 생성 직전 리스타일 모델을 CPU 로 내려 8GB VRAM 을 확보한다.

    _gpu_lock 은 '동시 실행'만 막고 '상주 메모리'는 비우지 못한다 — 리스타일 모델(약 2GB+)이
    남아 있으면 Wan 생성(피크 약 7.6GB)이 OOM 으로 실패하므로 반드시 스왑한다.
    """
    if _restyler is not None and _ACCEL_DEVICE == "cuda":
        _restyler.to_device("cpu")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _ensure_restyler_on_accel(restyler: HairRestyler) -> None:
    """리스타일 직전 모델을 가속 장치로 복귀시킨다(영상 생성이 CPU 로 내려놨을 수 있음)."""
    if _ACCEL_DEVICE == "cuda":
        torch.cuda.empty_cache()
        restyler.to_device(_ACCEL_DEVICE)


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

    async with _gpu_lock:
        restyler = _get_restyler()
        await asyncio.to_thread(_ensure_restyler_on_accel, restyler)
        result, _mask = await asyncio.to_thread(
            restyler.restyle,
            src,
            prompt=prompt,
            negative_prompt=negative_prompt,
            steps=steps,
            seed=seed,
        )
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def _run_video_command(command_template: str, request: VideoRenderRequest) -> bytes:
    with tempfile.TemporaryDirectory(prefix="hairso-video-") as tmp:
        tmpdir = Path(tmp)
        input_path = tmpdir / "source"
        output_path = tmpdir / "output.mp4"
        prompt_path = tmpdir / "prompt.txt"
        meta_path = tmpdir / "request.env"

        if request.image_bytes is not None:
            input_path.write_bytes(request.image_bytes)
        prompt_path.write_text(request.prompt, encoding="utf-8")
        meta_path.write_text(
            "\n".join(
                [
                    f"duration_seconds={request.duration_seconds}",
                    f"aspect_ratio={request.aspect_ratio}",
                    f"quality={request.quality}",
                    f"idempotency_key={request.idempotency_key}",
                    f"model={request.model or ''}",
                    f"negative_prompt={request.negative_prompt or ''}",
                    f"seed={request.seed if request.seed is not None else ''}",
                ]
            ),
            encoding="utf-8",
        )

        args = [
            part.format(
                input=str(input_path) if request.image_bytes is not None else "",
                output=str(output_path),
                prompt_file=str(prompt_path),
                meta_file=str(meta_path),
            )
            for part in _split_command(command_template)
        ]
        try:
            completed = subprocess.run(
                args,
                check=False,
                cwd=str(tmpdir),
                capture_output=True,
                timeout=int(os.environ.get("LOCAL_VIDEO_RENDER_TIMEOUT_SECONDS", "3600")),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WanVideoGenerationError("LOCAL_VIDEO_RENDER_FAILED") from exc

        if completed.returncode != 0 or not output_path.is_file():
            raise WanVideoGenerationError("LOCAL_VIDEO_RENDER_FAILED")
        data = output_path.read_bytes()
        if not _is_probable_mp4(data):
            raise WanVideoGenerationError("LOCAL_VIDEO_RENDER_INVALID_MP4")
        return data


def _render_video_sync(request: VideoRenderRequest) -> bytes:
    command_template = os.environ.get("LOCAL_VIDEO_RENDER_COMMAND", "").strip()
    if command_template:
        return _run_video_command(command_template, request)
    return _get_wan_video_generator().generate(
        image_bytes=request.image_bytes,
        prompt=request.prompt,
        duration_seconds=request.duration_seconds,
        aspect_ratio=request.aspect_ratio,
        quality=request.quality,
        model=request.model,
        negative_prompt=request.negative_prompt,
        seed=request.seed,
    )


def _is_probable_mp4(data: bytes) -> bool:
    return len(data) >= 12 and b"ftyp" in data[:32]


def _split_command(command_template: str) -> list[str]:
    if os.name != "nt":
        return shlex.split(command_template)
    parts = shlex.split(command_template, posix=False)
    return [
        part[1:-1]
        if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"}
        else part
        for part in parts
    ]


def _job_payload(job: VideoJob) -> dict[str, str | None]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "error_code": job.error_code,
    }


async def _run_video_job(job_id: str, request: VideoRenderRequest) -> None:
    job = _video_jobs.get(job_id)
    if job is None:
        return

    async with _gpu_lock:
        job.status = "PROCESSING"
        job.error_code = None
        try:
            await asyncio.to_thread(_release_gpu_for_video)
            data = await asyncio.to_thread(_render_video_sync, request)
        except WanVideoGenerationError as exc:
            job.status = "FAILED"
            job.error_code = str(exc) or "LOCAL_VIDEO_RENDER_FAILED"
            return
        except Exception:
            job.status = "FAILED"
            job.error_code = "LOCAL_VIDEO_RENDER_FAILED"
            return
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        if not _is_probable_mp4(data):
            job.status = "FAILED"
            job.error_code = "LOCAL_VIDEO_RENDER_INVALID_MP4"
            return

        job.video_bytes = data
        job.status = "SUCCEEDED"


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
) -> JSONResponse:
    """영상 생성 job 을 등록하고 즉시 반환한다."""
    existing_job_id = _video_job_by_idempotency_key.get(idempotency_key)
    if existing_job_id is not None:
        existing_job = _video_jobs.get(existing_job_id)
        if existing_job is not None:
            return JSONResponse(_job_payload(existing_job), status_code=202)

    request = VideoRenderRequest(
        image_bytes=await image.read() if image is not None else None,
        prompt=prompt,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        quality=quality,
        idempotency_key=idempotency_key,
        model=model,
        negative_prompt=negative_prompt,
        seed=seed,
    )
    job = VideoJob(job_id=f"wan-{uuid.uuid4()}")
    _video_jobs[job.job_id] = job
    _video_job_by_idempotency_key[idempotency_key] = job.job_id
    asyncio.create_task(_run_video_job(job.job_id, request))
    return JSONResponse(_job_payload(job), status_code=202)


@app.get("/video/i2v/{job_id}")
async def video_i2v_status(job_id: str) -> dict[str, str | None]:
    job = _video_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="LOCAL_VIDEO_JOB_NOT_FOUND")
    return _job_payload(job)


@app.get("/video/i2v/{job_id}/output")
async def video_i2v_output(job_id: str) -> Response:
    job = _video_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="LOCAL_VIDEO_JOB_NOT_FOUND")
    if job.status != "SUCCEEDED" or job.video_bytes is None:
        raise HTTPException(status_code=409, detail="LOCAL_VIDEO_JOB_NOT_READY")
    return Response(content=job.video_bytes, media_type="video/mp4")
