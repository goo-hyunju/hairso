from __future__ import annotations

import inspect
import logging
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

# 원인 예외를 서버 로그로만 남긴다. 이미지 바이트·프롬프트 본문은 로그에 남기지 않는다(§0.15).
_LOGGER = logging.getLogger("hairso.wan_video")

_DEFAULT_MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
_DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, distorted, deformed, watermark, text, logo, "
    "extra limbs, duplicated objects, flicker"
)
_QUALITY_SIZES = {
    "480p": (832, 480),
    "720p": (1280, 704),
}


class WanVideoGenerationError(RuntimeError):
    """Raised when the local Wan video pipeline cannot produce a valid MP4."""


@dataclass(frozen=True)
class WanVideoRequest:
    prompt: str
    image_bytes: bytes | None
    duration_seconds: int
    aspect_ratio: str
    quality: str
    model: str | None
    negative_prompt: str | None
    seed: int | None


class WanVideoGenerator:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        transformer_gguf: str | None = None,
        device: str | None = None,
    ) -> None:
        self._model_id = model_id or os.environ.get("WAN_VIDEO_MODEL_ID") or _DEFAULT_MODEL_ID
        self._transformer_gguf = transformer_gguf or os.environ.get("WAN_VIDEO_TRANSFORMER_GGUF")
        self._requested_device = device or os.environ.get("WAN_VIDEO_DEVICE") or "auto"
        # 모드별 래퍼("i2v"/"t2v")를 분리 캐시한다. 가중치 컴포넌트는 from_pipe 로 공유되므로
        # 두 번째 모드가 추가 메모리를 쓰지 않는다. 단일 캐시로 재사용하면 I2V 로 로드된
        # 파이프라인에 텍스트 전용 요청이 들어가 호출이 실패한다.
        self._pipes: dict[str, Any] = {}
        self._torch: Any | None = None
        self._device = "cpu"

    def generate(
        self,
        *,
        image_bytes: bytes | None,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        quality: str,
        model: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        request = WanVideoRequest(
            prompt=prompt.strip(),
            image_bytes=image_bytes,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            quality=quality,
            model=model,
            negative_prompt=negative_prompt,
            seed=seed,
        )
        if not request.prompt:
            raise WanVideoGenerationError("WAN_VIDEO_PROMPT_REQUIRED")

        if request.model and request.model != self._model_id:
            if self._pipes:
                raise WanVideoGenerationError("WAN_VIDEO_MODEL_ALREADY_LOADED")
            self._model_id = request.model

        height, width = _resolve_size(request.quality, request.aspect_ratio)
        fps = _env_int("WAN_VIDEO_FPS", 24)
        seconds = _clamp_duration(request.duration_seconds)
        frames = _frame_count(seconds, fps)
        steps = _env_int("WAN_VIDEO_NUM_INFERENCE_STEPS", 20)
        guidance_scale = _env_float("WAN_VIDEO_GUIDANCE_SCALE", 5.0)
        image = _decode_image(request.image_bytes, width=width, height=height)
        pipe = self._load_pipeline(wants_image=image is not None)
        _LOGGER.info(
            "wan generate start: model=%s device=%s size=%dx%d frames=%d steps=%d i2v=%s",
            self._model_id, self._device, width, height, frames, steps, image is not None,
        )

        kwargs = self._build_call_kwargs(
            pipe=pipe,
            prompt=request.prompt,
            image=image,
            negative_prompt=request.negative_prompt or _DEFAULT_NEGATIVE_PROMPT,
            height=height,
            width=width,
            num_frames=frames,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            seed=request.seed,
        )

        try:
            result = pipe(**kwargs)
        except TypeError as exc:
            _LOGGER.exception("wan pipeline call TypeError (pipe=%s)", type(pipe).__name__)
            if image is not None and "image" in kwargs:
                raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_IMAGE_INPUT_UNSUPPORTED") from exc
            raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_CALL_FAILED") from exc
        except Exception as exc:
            _LOGGER.exception("wan pipeline call failed (pipe=%s)", type(pipe).__name__)
            raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_CALL_FAILED") from exc

        return _export_mp4(_extract_frames(result), fps=fps)

    def _load_pipeline(self, *, wants_image: bool) -> Any:
        key = "i2v" if wants_image else "t2v"
        cached = self._pipes.get(key)
        if cached is not None:
            return cached

        try:
            import torch
            import diffusers
        except Exception as exc:
            raise WanVideoGenerationError("WAN_VIDEO_DEPENDENCY_MISSING") from exc

        base = next(iter(self._pipes.values()), None)
        if base is not None:
            pipe = self._derive_pipeline(diffusers, base, wants_image=wants_image)
            self._pipes[key] = pipe
            return pipe

        self._torch = torch
        self._device = _resolve_device(torch, self._requested_device)
        dtype = _resolve_dtype(torch, os.environ.get("WAN_VIDEO_DTYPE"))
        pipeline_kwargs: dict[str, Any] = {"torch_dtype": dtype}
        pipeline_class = getattr(diffusers, "DiffusionPipeline")
        if wants_image:
            pipeline_class = getattr(diffusers, "WanImageToVideoPipeline", pipeline_class)

        if self._transformer_gguf:
            pipeline_kwargs["transformer"] = self._load_gguf_transformer(dtype=dtype)

        try:
            pipe = pipeline_class.from_pretrained(self._model_id, **pipeline_kwargs)
        except TypeError:
            legacy_kwargs = dict(pipeline_kwargs)
            if "torch_dtype" in legacy_kwargs:
                legacy_kwargs["dtype"] = legacy_kwargs.pop("torch_dtype")
            pipe = pipeline_class.from_pretrained(self._model_id, **legacy_kwargs)
        except Exception as exc:
            _LOGGER.exception("wan model load failed (model=%s)", self._model_id)
            raise WanVideoGenerationError("WAN_VIDEO_MODEL_LOAD_FAILED") from exc

        vae = getattr(pipe, "vae", None)
        if vae is not None and hasattr(vae, "enable_tiling"):
            vae.enable_tiling()

        self._place_pipeline(pipe, torch)

        self._pipes[key] = pipe
        return pipe

    def _derive_pipeline(self, diffusers: Any, base: Any, *, wants_image: bool) -> Any:
        """로드된 파이프라인의 컴포넌트를 공유해 반대 모드(T2V/I2V) 래퍼를 만든다.

        가중치 재로드가 없고, 오프로딩 훅은 모듈에 붙어 있어 그대로 따라온다.
        """
        class_name = "WanImageToVideoPipeline" if wants_image else "WanPipeline"
        pipeline_class = getattr(diffusers, class_name, None)
        if pipeline_class is None or not hasattr(pipeline_class, "from_pipe"):
            raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_MODE_UNSUPPORTED")
        try:
            pipe = pipeline_class.from_pipe(base)
        except Exception as exc:
            _LOGGER.exception("wan pipeline mode derive failed (target=%s)", class_name)
            raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_MODE_UNSUPPORTED") from exc
        vae = getattr(pipe, "vae", None)
        if vae is not None and hasattr(vae, "enable_tiling"):
            vae.enable_tiling()
        return pipe

    def _place_pipeline(self, pipe: Any, torch: Any) -> None:
        offload_mode = os.environ.get("WAN_VIDEO_OFFLOAD", "group").strip().lower()
        try:
            if self._device.startswith("cuda") and offload_mode == "group" and hasattr(pipe, "enable_group_offload"):
                offload_type = os.environ.get("WAN_VIDEO_GROUP_OFFLOAD_TYPE", "leaf_level")
                num_blocks_per_group = _env_optional_int("WAN_VIDEO_NUM_BLOCKS_PER_GROUP")
                if offload_type == "block_level" and num_blocks_per_group is None:
                    num_blocks_per_group = 1
                pipe.enable_group_offload(
                    onload_device=torch.device(self._device),
                    offload_device=torch.device("cpu"),
                    offload_type=offload_type,
                    num_blocks_per_group=num_blocks_per_group,
                    non_blocking=_env_bool("WAN_VIDEO_OFFLOAD_NON_BLOCKING", False),
                    use_stream=_env_bool("WAN_VIDEO_OFFLOAD_USE_STREAM", False),
                )
            elif self._device.startswith("cuda") and offload_mode != "none" and hasattr(pipe, "enable_model_cpu_offload"):
                pipe.enable_model_cpu_offload()
            elif hasattr(pipe, "to"):
                pipe.to(self._device)
        except Exception as exc:
            _LOGGER.exception("wan model placement failed (offload=%s)", offload_mode)
            raise WanVideoGenerationError("WAN_VIDEO_MODEL_PLACEMENT_FAILED") from exc

    def _load_gguf_transformer(self, *, dtype: Any) -> Any:
        try:
            from diffusers import GGUFQuantizationConfig, WanTransformer3DModel
        except Exception as exc:
            raise WanVideoGenerationError("WAN_VIDEO_GGUF_DEPENDENCY_MISSING") from exc

        try:
            quantization_config = GGUFQuantizationConfig(compute_dtype=dtype)
            return WanTransformer3DModel.from_single_file(
                self._transformer_gguf,
                config=self._model_id,
                subfolder="transformer",
                quantization_config=quantization_config,
                torch_dtype=dtype,
            )
        except TypeError:
            quantization_config = GGUFQuantizationConfig(compute_dtype=dtype)
            return WanTransformer3DModel.from_single_file(
                self._transformer_gguf,
                config=self._model_id,
                subfolder="transformer",
                quantization_config=quantization_config,
                dtype=dtype,
            )
        except Exception as exc:
            raise WanVideoGenerationError("WAN_VIDEO_GGUF_LOAD_FAILED") from exc

    def _build_call_kwargs(
        self,
        *,
        pipe: Any,
        prompt: str,
        image: Any | None,
        negative_prompt: str,
        height: int,
        width: int,
        num_frames: int,
        num_inference_steps: int,
        guidance_scale: float,
        seed: int | None,
    ) -> dict[str, Any]:
        signature = inspect.signature(pipe.__call__)
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        accepted = set(signature.parameters)

        def accepts(name: str) -> bool:
            return accepts_kwargs or name in accepted

        kwargs: dict[str, Any] = {}
        candidates: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "height": height,
            "width": width,
            "num_frames": num_frames,
            "num_inference_steps": num_inference_steps,
            "guidance_scale": guidance_scale,
            "output_type": os.environ.get("WAN_VIDEO_OUTPUT_TYPE", "np"),
        }

        for key, value in candidates.items():
            if accepts(key):
                kwargs[key] = value

        if image is not None:
            if accepts("image"):
                kwargs["image"] = image
            else:
                raise WanVideoGenerationError("WAN_VIDEO_PIPELINE_IMAGE_INPUT_UNSUPPORTED")

        if seed is not None and accepts("generator") and self._torch is not None:
            generator_device = "cuda" if self._device.startswith("cuda") else "cpu"
            kwargs["generator"] = self._torch.Generator(device=generator_device).manual_seed(seed)

        return kwargs


def _resolve_device(torch: Any, requested_device: str) -> str:
    if requested_device != "auto":
        return requested_device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_dtype(torch: Any, requested_dtype: str | None) -> Any:
    if requested_dtype == "float32":
        return torch.float32
    if requested_dtype == "float16":
        return torch.float16
    return torch.bfloat16 if torch.cuda.is_available() else torch.float32


def _resolve_size(quality: str, aspect_ratio: str) -> tuple[int, int]:
    normalized_quality = "720p" if quality == "720p" else "480p"
    height, width = _QUALITY_SIZES[normalized_quality]
    if aspect_ratio == "16:9":
        return width, height
    return height, width


def _clamp_duration(duration_seconds: int) -> int:
    max_seconds = _env_int("WAN_VIDEO_MAX_SECONDS", 5)
    return max(1, min(duration_seconds, max_seconds))


def _frame_count(seconds: int, fps: int) -> int:
    candidate = max(1, seconds * max(1, fps))
    remainder = candidate % 4
    if remainder == 1:
        return candidate
    return candidate + ((1 - remainder) % 4)


def _decode_image(image_bytes: bytes | None, *, width: int, height: int) -> Any | None:
    if image_bytes is None:
        return None

    try:
        from PIL import Image
    except Exception as exc:
        raise WanVideoGenerationError("WAN_VIDEO_PIL_DEPENDENCY_MISSING") from exc

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise WanVideoGenerationError("WAN_VIDEO_INVALID_SOURCE_IMAGE") from exc

    return _resize_cover(image, width=width, height=height)


def _resize_cover(image: Any, *, width: int, height: int) -> Any:
    target_ratio = width / height
    source_ratio = image.width / image.height

    if source_ratio > target_ratio:
        crop_width = int(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif source_ratio < target_ratio:
        crop_height = int(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    try:
        from PIL import Image
    except Exception as exc:
        raise WanVideoGenerationError("WAN_VIDEO_PIL_DEPENDENCY_MISSING") from exc

    return image.resize((width, height), Image.Resampling.LANCZOS)


def _extract_frames(result: Any) -> list[Any]:
    frames = getattr(result, "frames", None)
    if frames is None and isinstance(result, dict):
        frames = result.get("frames")
    if frames is None:
        frames = getattr(result, "images", None)
    if frames is None and isinstance(result, dict):
        frames = result.get("images")

    if frames is None:
        raise WanVideoGenerationError("WAN_VIDEO_EMPTY_OUTPUT")

    if isinstance(frames, tuple):
        frames = list(frames)
    if hasattr(frames, "ndim"):
        if frames.ndim == 5:
            frames = list(frames[0])
        elif frames.ndim == 4:
            frames = list(frames)
        else:
            raise WanVideoGenerationError("WAN_VIDEO_EMPTY_OUTPUT")
    if isinstance(frames, list) and frames and isinstance(frames[0], (list, tuple)):
        frames = list(frames[0])

    if not isinstance(frames, list) or not frames:
        raise WanVideoGenerationError("WAN_VIDEO_EMPTY_OUTPUT")
    return frames


def _export_mp4(frames: list[Any], *, fps: int) -> bytes:
    try:
        from diffusers.utils import export_to_video
    except Exception as exc:
        raise WanVideoGenerationError("WAN_VIDEO_EXPORT_DEPENDENCY_MISSING") from exc

    with tempfile.TemporaryDirectory(prefix="hairso-wan-") as temp_dir:
        output_path = Path(temp_dir) / "output.mp4"
        try:
            export_to_video(frames, str(output_path), fps=fps)
            data = output_path.read_bytes()
        except Exception as exc:
            _LOGGER.exception("wan mp4 export failed (frames=%d fps=%d)", len(frames), fps)
            raise WanVideoGenerationError("WAN_VIDEO_EXPORT_FAILED") from exc

    if not _is_probable_mp4(data):
        raise WanVideoGenerationError("WAN_VIDEO_INVALID_MP4")
    return data


def _is_probable_mp4(data: bytes) -> bool:
    return len(data) >= 12 and data[4:8] == b"ftyp"


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
