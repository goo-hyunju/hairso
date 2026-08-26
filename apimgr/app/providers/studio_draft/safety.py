"""Studio draft prompt safety helpers.

Provider prompt 로 들어가면 안 되는 media reference, signed URL, Base64 형태를 탐지한다.
"""

from __future__ import annotations

import re


class SensitiveTextError(ValueError):
    """Studio draft prompt 에 넣을 수 없는 문자열."""


_FORBIDDEN_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"data:image", re.IGNORECASE),
    re.compile(r"\bbase64\b", re.IGNORECASE),
    re.compile(r"\bstorage[_ -]?key\b", re.IGNORECASE),
    re.compile(r"\bsigned[_ -]?url\b", re.IGNORECASE),
    re.compile(r"\bx-amz-signature\b", re.IGNORECASE),
    re.compile(r"\btoken=", re.IGNORECASE),
    re.compile(r"/storage/v1/object", re.IGNORECASE),
    re.compile(
        r"\b(?:face|generated|studio/outputs)/[A-Za-z0-9_-]{16,}\.(?:png|jpe?g|webp|mp4)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b"),
]


def assert_safe_draft_text(value: str | None, field_name: str) -> None:
    if value is None:
        return
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(value):
            raise SensitiveTextError(f"{field_name} contains a sensitive media reference")

