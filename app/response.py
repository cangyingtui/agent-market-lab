from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def success_payload(data: Any, message: str = "success") -> dict[str, Any]:
    payload = {"code": 0, "message": message, "data": data}
    if isinstance(data, dict):
        # 过渡期保留旧字段，避免脚本和调试调用一次性全部失效。
        payload.update(data)
    return payload


def error_code_for_status(status_code: int) -> str:
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    return "ERROR"


def error_payload(code: str, message: str, data: Any | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data or {},
        "detail": message,
    }


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or error_code_for_status(exc.status_code))
        message = str(detail.get("message") or detail.get("detail") or "请求失败")
        data = detail.get("data") or {}
    else:
        code = error_code_for_status(exc.status_code)
        message = str(detail)
        data = {}
    return JSONResponse(status_code=exc.status_code, content=error_payload(code, message, data))


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "请求参数校验失败", {"errors": exc.errors()}),
    )
