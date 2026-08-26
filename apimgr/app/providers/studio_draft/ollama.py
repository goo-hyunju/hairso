"""Ollama 기반 Studio draft provider.

로컬 Ollama HTTP API 만 사용한다. 고객 이미지 바이트, URL, signed URL, Base64 는 prompt 에 넣지 않는다.
실패하거나 구조가 맞지 않으면 `StudioDraftProviderError` 를 던지고 Service 가 Mock 으로 fallback 한다.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from app.domain.studio import StudioDraft, StudioScene, StudioScript
from app.providers.studio_draft.base import (
    StudioDraftInput,
    StudioDraftProvider,
    StudioDraftProviderError,
)
from app.providers.studio_draft.safety import SensitiveTextError, assert_safe_draft_text

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal", "ollama"}


class OllamaStudioDraftProvider(StudioDraftProvider):
    def __init__(self, base_url: str, model: str, timeout_s: float = 60.0) -> None:
        parsed = urlparse(base_url)
        if parsed.hostname not in _LOCAL_HOSTS:
            raise StudioDraftProviderError("ollama base url must point to a local host")
        if not model.strip():
            raise StudioDraftProviderError("ollama studio draft model is not configured")
        self._base_url = base_url.rstrip("/")
        self._model = model.strip()
        self._timeout = timeout_s

    def create_draft(self, data: StudioDraftInput) -> StudioDraft:
        payload = {
            "model": self._model,
            "system": _system_prompt(),
            "prompt": _user_prompt(data),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.4,
            },
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise StudioDraftProviderError("ollama draft request failed") from exc

        raw = body.get("response")
        if not isinstance(raw, str):
            raise StudioDraftProviderError("ollama draft response missing content")
        return _parse_draft(raw, data.duration_seconds)


def _system_prompt() -> str:
    return (
        "You create structured JSON drafts for a Korean short-form video studio. "
        "Return JSON only. Korean text must be used for hook, narration, cta, and captions. "
        "English must be used for visual_prompt. visual_prompt must describe image-to-video "
        "motion, camera movement, realistic lighting, and vertical 9:16 framing. Preserve "
        "face identity when a person is implied. Do not include URLs, storage keys, Base64, "
        "provider names, markdown, or comments. For HEALTH content, avoid diagnosis, treatment "
        "claims, dosage, or unreviewed medical facts; keep it informational and add caution."
    )


def _user_prompt(data: StudioDraftInput) -> str:
    _assert_input_safe(data)
    scene_hint = "3 scenes" if data.duration_seconds == 15 else "5 scenes"
    disclaimer = data.disclaimer or "none"
    audience = data.target_audience or "국내 시청자"
    return f"""
Create a Studio draft JSON object with this exact shape:
{{
  "version": 1,
  "script": {{
    "hook": "Korean hook for the first 3 seconds",
    "narration": ["1 to 6 Korean narration lines"],
    "cta": "Korean call to action"
  }},
  "storyboard": [
    {{
      "scene_index": 1,
      "duration_seconds": 5,
      "caption": "Korean on-screen caption",
      "visual_prompt": "English image-to-video prompt"
    }}
  ]
}}

Rules:
- Total storyboard duration must equal {data.duration_seconds} seconds.
- Use {scene_hint}. Each scene duration must be 5 to 8 seconds.
- Captions must be short Korean text for mobile vertical video.
- visual_prompt must be English and suitable for image-to-video generation.
- Mention uploaded media only as "uploaded reference images"; do not invent URLs.

Project:
- template_type: {data.template_type.value}
- category: {data.category.value}
- title: {data.title}
- offer_text: {data.offer_text}
- cta_text: {data.cta_text}
- target_audience: {audience}
- tone: {data.tone.value}
- uploaded_asset_count: {data.asset_count}
- has_logo: {data.has_logo}
- disclaimer: {disclaimer}
""".strip()


def _assert_input_safe(data: StudioDraftInput) -> None:
    try:
        assert_safe_draft_text(data.title, "title")
        assert_safe_draft_text(data.offer_text, "offer_text")
        assert_safe_draft_text(data.cta_text, "cta_text")
        assert_safe_draft_text(data.target_audience, "target_audience")
        assert_safe_draft_text(data.disclaimer, "disclaimer")
    except SensitiveTextError as exc:
        raise StudioDraftProviderError("ollama draft input contains sensitive text") from exc


def _parse_draft(raw: str, expected_duration_seconds: int) -> StudioDraft:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        raise StudioDraftProviderError("ollama draft response is not valid json") from exc
    if not isinstance(payload, dict):
        raise StudioDraftProviderError("ollama draft response must be an object")

    script_payload = payload.get("script")
    storyboard_payload = payload.get("storyboard")
    if not isinstance(script_payload, dict) or not isinstance(storyboard_payload, list):
        raise StudioDraftProviderError("ollama draft response has invalid shape")

    script = _parse_script(script_payload)
    storyboard = _parse_storyboard(storyboard_payload, expected_duration_seconds)
    return StudioDraft(script=script, storyboard=storyboard)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_script(payload: dict[str, Any]) -> StudioScript:
    hook = _required_text(payload.get("hook"), "script.hook", 240)
    cta = _required_text(payload.get("cta"), "script.cta", 120)
    narration_payload = payload.get("narration")
    if not isinstance(narration_payload, list):
        raise StudioDraftProviderError("script.narration must be a list")
    narration = [
        _required_text(item, "script.narration", 240)
        for item in narration_payload
        if isinstance(item, str) and item.strip()
    ]
    if not 1 <= len(narration) <= 6:
        raise StudioDraftProviderError("script.narration length is invalid")
    return StudioScript(hook=hook, narration=narration, cta=cta)


def _parse_storyboard(payload: list[Any], expected_duration_seconds: int) -> list[StudioScene]:
    if not 1 <= len(payload) <= 12:
        raise StudioDraftProviderError("storyboard length is invalid")

    scenes: list[StudioScene] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise StudioDraftProviderError("storyboard scene must be an object")
        duration = _required_int(item.get("duration_seconds"), "duration_seconds", 5, 8)
        scenes.append(
            StudioScene(
                scene_index=index,
                duration_seconds=duration,
                caption=_required_text(item.get("caption"), "caption", 160),
                visual_prompt=_required_text(item.get("visual_prompt"), "visual_prompt", 400),
            )
        )

    total = sum(scene.duration_seconds for scene in scenes)
    if total != expected_duration_seconds:
        raise StudioDraftProviderError("storyboard duration total is invalid")
    return scenes


def _required_text(value: Any, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise StudioDraftProviderError(f"{field_name} must be a string")
    text = value.strip()
    if not text or len(text) > max_length:
        raise StudioDraftProviderError(f"{field_name} length is invalid")
    try:
        assert_safe_draft_text(text, field_name)
    except SensitiveTextError as exc:
        raise StudioDraftProviderError(f"{field_name} contains sensitive text") from exc
    return text


def _required_int(value: Any, field_name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudioDraftProviderError(f"{field_name} must be an integer")
    if not minimum <= value <= maximum:
        raise StudioDraftProviderError(f"{field_name} is out of range")
    return value
