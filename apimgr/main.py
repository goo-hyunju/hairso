"""apimgr FastAPI 앱 진입점.

라우터를 등록한다. 무거운 작업은 Worker 로 분리(BackgroundTasks 단독 금지, §10).
오류는 공통 envelope { "error": { "error_code", "message", "request_id" } } 로 변환한다
(FastAPI 기본 { "detail": ... } 형식이 FE 계약과 다르므로 핸들러로 통일 — #3).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import consultations, generations, health, style, webhooks
from app.domain.enums import ErrorCode

app = FastAPI(
    title="HairView AI — apimgr",
    version="0.1.0",
    description="AI 헤어스타일 상담 및 영상 시뮬레이션 백엔드 (스캐폴드)",
)

# HTTP status -> 내부 오류코드 기본 매핑.
_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.GENERATION_DUPLICATED,
    429: ErrorCode.PROVIDER_RATE_LIMITED,
}
_VALID_CODES = {c.value for c in ErrorCode}


def _envelope(status_code: int, error_code: str, message: str, request_id: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"error_code": error_code, "message": message, "request_id": request_id}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # detail 이 내부 오류코드 문자열이면 그대로, 아니면 status 로 매핑.
    detail = str(exc.detail) if exc.detail is not None else ""
    if detail in _VALID_CODES:
        code = detail
    else:
        code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR).value
    request_id = request.headers.get("x-request-id")
    return _envelope(exc.status_code, code, detail or code, request_id)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    # 원문 오류 상세를 사용자에게 노출하지 않는다(§3.12) — 코드만.
    return _envelope(422, ErrorCode.VALIDATION_ERROR.value, "요청 형식을 확인해 주세요.", request_id)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 미처리 예외(500)도 envelope 로 통일하고 스택·원문은 노출하지 않는다(§3.12).
    # 실서비스는 여기서 서버측 구조화 로깅(스택 포함, 사용자 미노출)을 수행한다(로드맵).
    request_id = request.headers.get("x-request-id")
    return _envelope(500, ErrorCode.INTERNAL_ERROR.value, "일시적인 오류가 발생했어요.", request_id)


app.include_router(health.router)
app.include_router(consultations.router)
app.include_router(style.router)
app.include_router(generations.router)
app.include_router(webhooks.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "apimgr", "docs": "/docs"}
