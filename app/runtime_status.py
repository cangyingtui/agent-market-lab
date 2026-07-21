from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.time_utils import utc_now_naive


REPORT_WAITING_STATUS = "report_waiting"
REPORT_WAITING_STAGE = "report_generation_waiting"
RUNTIME_META_KEY = "_runtime"


def parse_utc_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def format_utc_iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def report_duration_bounds(plan_type: str | None) -> tuple[int, int]:
    if str(plan_type or "basic") == "pro":
        min_seconds = settings.pro_report_min_seconds
        max_seconds = settings.pro_report_max_seconds
    else:
        min_seconds = settings.basic_report_min_seconds
        max_seconds = settings.basic_report_max_seconds
    min_seconds = max(0, int(min_seconds or 0))
    max_seconds = max(0, int(max_seconds or 0))
    if max_seconds < min_seconds:
        max_seconds = min_seconds
    return min_seconds, max_seconds


def target_report_duration_seconds(task_id: str | None, plan_type: str | None) -> int:
    min_seconds, max_seconds = report_duration_bounds(plan_type)
    if max_seconds <= 0:
        return 0
    if min_seconds == max_seconds:
        return min_seconds
    seed = f"{plan_type or 'basic'}:{task_id or ''}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    offset = int.from_bytes(digest[:8], "big") % (max_seconds - min_seconds + 1)
    return min_seconds + offset


def estimate_task_total_seconds(task_id: str | None, plan_type: str | None) -> int:
    target = target_report_duration_seconds(task_id, plan_type)
    if target > 0:
        return target
    if str(plan_type or "basic") == "pro":
        return int(settings.pro_task_estimate_seconds)
    return int(settings.basic_task_estimate_seconds)


def attach_report_wait_runtime(
    result_data: dict[str, Any],
    task_id: str,
    plan_type: str | None,
    started_at: datetime | None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at or utc_now_naive()
    started = started_at or now
    target_seconds = target_report_duration_seconds(task_id, plan_type)
    ready_at = max(now, started + timedelta(seconds=target_seconds))
    meta = result_data.get(RUNTIME_META_KEY) if isinstance(result_data.get(RUNTIME_META_KEY), dict) else {}
    meta = {
        **meta,
        "report_wait_started_at": format_utc_iso(now),
        "report_ready_at": format_utc_iso(ready_at),
        "report_wait_target_seconds": target_seconds,
        "report_wait_plan_type": plan_type or "basic",
        "report_wait_task_id": task_id,
    }
    result_data[RUNTIME_META_KEY] = meta
    return meta


def report_wait_runtime(result_data: Any) -> dict[str, Any]:
    if not isinstance(result_data, dict):
        return {}
    meta = result_data.get(RUNTIME_META_KEY)
    return meta if isinstance(meta, dict) else {}


def report_ready_at(result_data: Any) -> datetime | None:
    return parse_utc_iso(report_wait_runtime(result_data).get("report_ready_at"))


def report_wait_started_at(result_data: Any) -> datetime | None:
    return parse_utc_iso(report_wait_runtime(result_data).get("report_wait_started_at"))


def report_wait_target_seconds(result_data: Any) -> int:
    value = report_wait_runtime(result_data).get("report_wait_target_seconds")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def report_wait_remaining_seconds(result_data: Any, now: datetime | None = None) -> int:
    ready_at = report_ready_at(result_data)
    if not ready_at:
        return 0
    current = now or utc_now_naive()
    return max(0, int((ready_at - current).total_seconds()))


def report_wait_progress_percent(result_data: Any, now: datetime | None = None) -> int:
    target_seconds = report_wait_target_seconds(result_data)
    started_at = report_wait_started_at(result_data)
    if target_seconds <= 0 or not started_at:
        return 99 if report_wait_remaining_seconds(result_data, now) > 0 else 100
    current = now or utc_now_naive()
    elapsed = max(0, int((current - started_at).total_seconds()))
    waiting_ratio = min(1.0, elapsed / max(1, target_seconds))
    return min(99, max(92, 92 + int(waiting_ratio * 7)))


def report_wait_progress_extra(result_data: Any, now: datetime | None = None) -> dict[str, Any]:
    ready_at = report_ready_at(result_data)
    started_at = report_wait_started_at(result_data)
    remaining = report_wait_remaining_seconds(result_data, now)
    return {
        "report_wait_started_at": format_utc_iso(started_at) if started_at else None,
        "report_ready_at": format_utc_iso(ready_at) if ready_at else None,
        "estimated_completed_at": format_utc_iso(ready_at) if ready_at else None,
        "remaining_seconds": remaining,
        "report_wait_target_seconds": report_wait_target_seconds(result_data),
    }
