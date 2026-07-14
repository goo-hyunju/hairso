"""공통 스키마 — 오류 envelope(snake_case).

와이어 오류 형식(D2): { "error": { "error_code", "message", "request_id" } }
CLAUDE §3.12 의 requestId(camel) 는 개발자 로그 전용이며 와이어가 아니다.
성공 응답은 envelope 로 감싸지 않는다(비대칭) — 클라이언트는 HTTP status 로 분기한다.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.enums import ErrorCode


class ErrorBody(BaseModel):
    error_code: ErrorCode
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
