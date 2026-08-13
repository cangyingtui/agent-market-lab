from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import case as sql_case, delete, func, inspect, or_, select, text
from sqlalchemy.orm import Session, defer

from app.assistant_service import build_assistant_response
from app.config import settings
from app.crowd_profile import canonicalize_market_crowds, crowd_profile_text, validate_crowd_segments
from app.custom_competitor_backfill import enqueue_project_backfill
from app.database import SessionLocal, engine, get_db
from app.export_service import (
    build_report_payload,
    check_pdf_render_prerequisites,
    decode_pdf_render_token,
    export_file_path,
    sanitize_web_report,
    with_project_report_fallbacks,
    write_export_file,
)
from app.models import (
    CustomCompetitorBackfillJob,
    DistillCheckLog,
    ExportTask,
    MarketCrowdTemplate,
    MarketSceneTemplate,
    MarketStrategyTemplate,
    Product,
    ProductCategory,
    ProductFieldTemplate,
    QuotaLog,
    RagTraceLog,
    ShareToken,
    SimulationProject,
    SimulationTaskLog,
    SystemFeatureFlag,
    UpgradeLog,
    User,
)
from app.price_enrichment import enqueue_product_price_enrichment
from app.redis_client import get_redis_client, redis_json_get, redis_json_set
from app.response import http_exception_handler, success_payload, validation_exception_handler
from app.runtime_status import (
    REPORT_WAITING_STAGE,
    REPORT_WAITING_STATUS,
    estimate_task_total_seconds,
    format_utc_iso,
    report_wait_progress_extra,
    report_wait_progress_percent,
    report_wait_remaining_seconds,
    target_report_duration_seconds,
)
from app.schemas import (
    AssistantChatRequest,
    AvatarUploadRequest,
    CreateSimulationRequest,
    DistillDebugRequest,
    ExportRequest,
    LoginRequest,
    RagSearchRequest,
    RegisterRequest,
    ShareTokenRequest,
    Step1Request,
    Step2Request,
    SubmitSimulationRequest,
    UpdateSimulationDraftRequest,
    UpdateUserProfileRequest,
    UpgradeUserRequest,
    WhatIfRequest,
)
from app.security import create_access_token, get_current_user, hash_password, verify_password
from app.share_tokens import create_share_token, hash_share_token
from app.task_keys import cancel_key, export_progress_key, progress_key, project_lock_key, project_progress_key
from app.time_utils import utc_now_iso, utc_now_naive
from engine.distill_client import debug_distill_check as run_debug_distill_check
from engine.distill_client import run_distill_checks_if_enabled
from engine.chart_data import build_chart_data
from engine.social_network import representative_agent_count
from engine.maut_model import MAUT_WEIGHTS, build_decision_model_summary, decision_weight_profile, normalize_weights, safe_float as maut_safe_float, weighted_purchase_intent
from engine.commercial_model import MODEL_VERSION as COMMERCIAL_MODEL_VERSION
from engine.propagation_funnel import build_propagation_funnel
from knowledge_model.product_evidence import search_product_evidence
from knowledge_model.rag_service import get_rag_service
from scripts.product_ui_schema_loader import schema_for_field


app = FastAPI(title=settings.app_name)
logger = logging.getLogger(__name__)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


QUEUE_NAMES = (
    settings.redis_basic_queue,
    settings.redis_pro_queue,
    settings.redis_task_queue,
)
DEMO_ACCOUNT_USERNAMES = {"normal@example", "pro@example"}
ACTIVE_PROJECT_STATUSES = {"submitted", "queued", "running", REPORT_WAITING_STATUS}


@app.middleware("http")
async def wrap_json_response(request: Request, call_next) -> Response:
    response = await call_next(request)
    if request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        return response
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type or response.status_code >= 400:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    try:
        data = json.loads(body.decode("utf-8")) if body else None
    except json.JSONDecodeError:
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    if isinstance(data, dict) and {"code", "message", "data"}.issubset(data.keys()):
        content = data
    else:
        content = success_payload(data)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(
        content=content,
        status_code=response.status_code,
        headers=headers,
    )


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def category_to_dict(item: ProductCategory) -> dict[str, Any]:
    return {
        "id": item.id,
        "category": item.category,
        "subcategory": item.subcategory,
        "display_name": item.display_name,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


@lru_cache(maxsize=1)
def product_field_ui_schema_column_exists() -> bool:
    columns = {column["name"] for column in inspect(engine).get_columns("product_field_templates")}
    return "ui_schema" in columns


def field_to_dict(item: ProductFieldTemplate, category: ProductCategory | None = None) -> dict[str, Any]:
    schema: dict[str, Any] | None = None
    if product_field_ui_schema_column_exists():
        schema = item.ui_schema
    if not schema and category is not None:
        schema = schema_for_field(category.category, category.subcategory, item.field_name)
    return {
        "id": item.id,
        "category_id": item.category_id,
        "field_name": item.field_name,
        "field_type": item.field_type,
        "field_desc": item.field_desc,
        "unit": item.unit or (schema or {}).get("unit"),
        "ui_control": item.ui_control or (schema or {}).get("controlType"),
        "ui_schema": schema,
        "default_weight": item.default_weight,
        "is_required": item.is_required,
        "sort_order": item.sort_order,
    }


def product_to_dict(item: Product) -> dict[str, Any]:
    return {
        "id": item.id,
        "category_id": item.category_id,
        "category": item.category,
        "subcategory": item.subcategory,
        "product_name": item.product_name,
        "brand": item.brand,
        "confirmed_sku": item.confirmed_sku,
        "price_cny": item.price_cny,
        "specifications": item.specifications or {},
        "quality_status": item.quality_status,
        "source_file": item.source_file,
        "source_row": item.source_row,
        "collection_time": item.collection_time,
        "is_active": item.is_active,
    }


def crowd_to_dict(item: MarketCrowdTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "default_ratio": item.default_ratio,
        "tags": item.tags or {},
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def strategy_to_dict(item: MarketStrategyTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "default_params": item.default_params or {},
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def scene_to_dict(item: MarketSceneTemplate) -> dict[str, Any]:
    return {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "description": item.description,
        "default_weight": item.default_weight,
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def user_to_dict(user: User) -> dict[str, Any]:
    remaining = None if user.plan_type == "pro" else user.basic_quota_remaining
    return {
        "id": user.id,
        "user_id": user.id,
        "username": user.username,
        "nickname": user.full_name or user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url or "/api/user/avatar/default",
        "plan_type": user.plan_type,
        "version": user.plan_type,
        "is_demo_account": user.username in DEMO_ACCOUNT_USERNAMES,
        "basic_quota_remaining": user.basic_quota_remaining,
        "remaining_simulations": remaining,
        "pro_expire_at": user.pro_expire_at,
    }


def project_to_dict(
    project: SimulationProject,
    *,
    include_configs: bool = True,
    include_snapshot: bool = False,
    include_result: bool = False,
) -> dict[str, Any]:
    status_labels = {
        "draft": "未提交",
        "submitted": "已提交",
        "queued": "等待生成",
        "running": "生成中",
        REPORT_WAITING_STATUS: "报告生成中",
        "completed": "已完成",
        "failed": "生成中断",
        "cancelled": "已取消",
    }
    payload = {
        "id": project.id,
        "user_id": project.user_id,
        "project_name": project.project_name,
        "status": project.status,
        "status_label": status_labels.get(str(project.status or "").strip(), project.status),
        "plan_type_used": project.plan_type_used,
        "snapshot_hash": project.snapshot_hash,
        "task_id": project.task_id,
        "draft_version": project.draft_version,
        "simulation_version": project.simulation_version,
        "error_code": project.error_code,
        "error_reason": project.error_reason,
        "submitted_at": project.submitted_at,
        "started_at": project.started_at,
        "last_heartbeat_at": project.last_heartbeat_at,
        "completed_at": project.completed_at,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if include_configs:
        payload.update(
            {
                "product_definition": project.product_definition or {},
                "market_config": project.market_config or {},
            }
        )
    if include_snapshot:
        payload["config_snapshot"] = project.config_snapshot or {}
    if include_result:
        payload["result_data"] = project.result_data
    return payload


STAGE_FLOW = [
    {"key": "queued", "label": "等待开始", "percent": 0},
    {"key": "start", "label": "准备仿真", "percent": 10},
    {"key": "rag", "label": "整理市场证据", "percent": 18},
    {"key": "agent_generation", "label": "模拟目标用户", "percent": 32},
    {"key": "purchase_decision", "label": "计算购买意愿", "percent": 60},
    {"key": "social_propagation", "label": "多轮社交传播", "percent": 68},
    {"key": "aux_validation", "label": "校验分析结果", "percent": 80},
    {"key": "aggregation", "label": "汇总仿真指标", "percent": 82},
    {"key": "assemble_report", "label": "整理报告", "percent": 90},
    {"key": "report_generation_waiting", "label": "报告生成中", "percent": 96},
    {"key": "completed", "label": "完成", "percent": 100},
]


def normalize_stage(stage: Any) -> str:
    text_value = str(stage or "queued").strip()
    if text_value.startswith("rag"):
        return "rag"
    if text_value == "running":
        return "start"
    if text_value == REPORT_WAITING_STATUS:
        return REPORT_WAITING_STAGE
    if text_value in {"retry", "submitted"}:
        return "queued"
    if text_value in {"cancel_requested", "cancelled", "failed"}:
        return text_value
    keys = {item["key"] for item in STAGE_FLOW}
    return text_value if text_value in keys else "queued"


ACTIVE_DISPLAY_PROGRESS_STATUSES = {"queued", "submitted", "retrying", "running", REPORT_WAITING_STATUS}


def positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def progress_origin_at(project: SimulationProject, progress: dict[str, Any], status_text: str) -> datetime | None:
    created_at = parse_utc_iso(progress.get("created_at"))
    if status_text in {"queued", "submitted", "retrying"}:
        return created_at or project.submitted_at or parse_utc_iso(progress.get("estimated_start_at"))
    return created_at or project.started_at or project.submitted_at or parse_utc_iso(progress.get("estimated_start_at"))


def smooth_active_progress(project: SimulationProject, progress: dict[str, Any]) -> None:
    status_text = str(progress.get("status") or project.status or "")
    if status_text == "completed" or project.status == "completed":
        progress["percent"] = 100
        progress["remaining_seconds"] = 0
        return
    if status_text not in ACTIVE_DISPLAY_PROGRESS_STATUSES:
        return

    now = utc_now_naive()
    origin_at = progress_origin_at(project, progress, status_text)
    estimated_at = parse_utc_iso(progress.get("estimated_completed_at") or progress.get("report_ready_at"))
    configured_target = positive_int(progress.get("target_duration_seconds") or progress.get("report_wait_target_seconds"))
    if not configured_target and project.task_id:
        configured_target = estimate_task_total_seconds(project.task_id, project.plan_type_used)
    remaining = positive_int(progress.get("remaining_seconds") or progress.get("queue_eta_seconds")) or 0

    if estimated_at:
        remaining = max(0, int((estimated_at - now).total_seconds()))
    elif origin_at and configured_target:
        estimated_at = origin_at + timedelta(seconds=configured_target)
        remaining = max(0, int((estimated_at - now).total_seconds()))
        progress["estimated_completed_at"] = format_utc_iso(estimated_at)

    total_seconds = configured_target or 0
    if origin_at and estimated_at:
        total_seconds = max(total_seconds, int((estimated_at - origin_at).total_seconds()))
    if total_seconds <= 0:
        return

    if not estimated_at:
        elapsed = max(0, total_seconds - remaining)
    elif origin_at:
        elapsed = max(0, int((now - origin_at).total_seconds()))
    else:
        elapsed = max(0, total_seconds - remaining)

    ratio = min(1.0, max(0.0, elapsed / max(1, total_seconds)))
    start_percent = 3 if status_text in {"queued", "submitted", "retrying"} else 6
    end_percent = 99 if status_text == REPORT_WAITING_STATUS else 98
    smoothed_percent = min(end_percent, max(start_percent, round(start_percent + ratio * (end_percent - start_percent))))

    if "raw_percent" not in progress:
        progress["raw_percent"] = progress.get("percent")
    progress["percent"] = smoothed_percent
    progress["remaining_seconds"] = remaining
    progress["display_progress_mode"] = "time_smoothed"


def promote_report_waiting_if_ready(db: Session, project: SimulationProject) -> bool:
    if project.status != REPORT_WAITING_STATUS or not project.result_data:
        return False
    if report_wait_remaining_seconds(project.result_data) > 0:
        return False
    project.status = "completed"
    project.completed_at = project.completed_at or utc_now_naive()
    project.error_code = None
    project.error_reason = None
    db.add(project)
    db.commit()
    db.refresh(project)
    progress = {
        "task_id": project.task_id,
        "project_id": project.id,
        "status": "completed",
        "percent": 100,
        "stage": "completed",
        "message": "任务已完成",
        "remaining_seconds": 0,
        "report_waiting": False,
        "completed_at": format_utc_iso(project.completed_at) if project.completed_at else utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    try:
        if project.task_id:
            redis_json_set(progress_key(project.task_id), progress, ex=settings.redis_progress_expire_seconds)
        redis_json_set(project_progress_key(project.id), progress, ex=settings.redis_progress_expire_seconds)
    except Exception:
        pass
    return True


def build_progress_payload(project: SimulationProject, raw_progress: dict[str, Any] | None) -> dict[str, Any]:
    progress = dict(raw_progress or {})
    if not progress:
        progress = {
            "task_id": project.task_id,
            "project_id": project.id,
            "status": project.status,
            "percent": 100 if project.status == "completed" else 0,
            "stage": project.status,
            "message": project.error_reason or project.status,
            "updated_at": utc_now_iso(),
        }
    if project.status == "completed":
        progress.update(
            {
                "task_id": project.task_id,
                "project_id": project.id,
                "status": "completed",
                "percent": 100,
                "stage": "completed",
                "message": "任务已完成",
                "remaining_seconds": 0,
                "report_waiting": False,
                "completed_at": project.completed_at or utc_now_iso(),
            }
        )
    elif project.status == REPORT_WAITING_STATUS:
        now = utc_now_naive()
        wait_extra = report_wait_progress_extra(project.result_data or {}, now)
        progress.update(
            {
                "task_id": project.task_id,
                "project_id": project.id,
                "status": REPORT_WAITING_STATUS,
                "percent": report_wait_progress_percent(project.result_data or {}, now),
                "stage": REPORT_WAITING_STAGE,
                "message": "报告正在生成，请稍后",
                "report_waiting": True,
                "created_at": format_utc_iso(project.submitted_at) if project.submitted_at else progress.get("created_at"),
                "estimated_start_at": format_utc_iso(project.started_at) if project.started_at else wait_extra.get("report_wait_started_at"),
                "target_duration_seconds": wait_extra.get("report_wait_target_seconds"),
                **wait_extra,
            }
        )
    elif str(progress.get("status") or "") == "completed" and project.status != "completed":
        status = project.status or "running"
        if status in {"draft", "submitted"}:
            progress.update(
                {
                    "task_id": project.task_id,
                    "project_id": project.id,
                    "status": status,
                    "percent": 0,
                    "stage": status,
                    "message": "配置已修改，请重新提交仿真",
                    "remaining_seconds": None,
                    "report_waiting": False,
                }
            )
        else:
            progress.update(
                {
                    "task_id": project.task_id,
                    "project_id": project.id,
                    "status": "running",
                    "percent": min(98, int(_number_value(progress.get("percent"), 98))),
                    "stage": "assemble_report",
                    "message": "报告整理中，请稍后",
                    "report_waiting": True,
                }
            )
    current_stage = normalize_stage(progress.get("stage"))
    status_text = str(progress.get("status") or project.status)
    flow_keys = [item["key"] for item in STAGE_FLOW]
    current_index = flow_keys.index(current_stage) if current_stage in flow_keys else 0
    stages: list[dict[str, Any]] = []
    for index, item in enumerate(STAGE_FLOW):
        if status_text == "completed":
            stage_status = "done"
        elif status_text in {"failed", "cancelled"} and index == min(current_index, len(STAGE_FLOW) - 1):
            stage_status = "failed"
        elif status_text == "cancel_requested" and item["key"] == current_stage:
            stage_status = "current"
        elif index < current_index:
            stage_status = "done"
        elif index == current_index:
            stage_status = "current"
        else:
            stage_status = "pending"
        stages.append({**item, "status": stage_status})
    progress["current_stage"] = current_stage
    progress["stages"] = stages
    if project.task_id:
        queue_diagnostics = build_queue_diagnostics(project, progress)
        progress["queue_diagnostics"] = queue_diagnostics
        should_trust_queue_eta = status_text in {"queued", "submitted", "retrying"} and bool(queue_diagnostics.get("queue_eta_seconds"))
        for key in ("queue_eta_seconds", "estimated_start_at", "estimated_completed_at", "remaining_seconds"):
            if queue_diagnostics.get(key) is not None and (should_trust_queue_eta or progress.get(key) in (None, "", 0)):
                progress[key] = queue_diagnostics[key]
    smooth_active_progress(project, progress)
    return progress


def parse_utc_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return None


def redis_key_text(key: Any) -> str:
    return key.decode("utf-8", errors="ignore") if isinstance(key, bytes) else str(key)


def queue_item_text(raw_item: Any) -> str:
    return raw_item.decode("utf-8", errors="ignore") if isinstance(raw_item, bytes) else str(raw_item)


def decode_queue_item(raw_item: Any) -> dict[str, Any] | None:
    try:
        payload = json.loads(queue_item_text(raw_item))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def remove_task_from_queues(client: Any, task_id: str) -> int:
    removed = 0
    for queue_name in QUEUE_NAMES:
        for raw_item in client.lrange(queue_name, 0, -1):
            payload = decode_queue_item(raw_item)
            if payload and str(payload.get("task_id")) == str(task_id):
                removed += int(client.lrem(queue_name, 0, raw_item) or 0)
    return removed


def find_task_in_queues(client: Any, task_id: str | None) -> tuple[bool, str | None, int | None]:
    if not task_id:
        return False, None, None
    for queue_name in QUEUE_NAMES:
        for index, raw_item in enumerate(client.lrange(queue_name, 0, -1)):
            payload = decode_queue_item(raw_item)
            if payload and str(payload.get("task_id")) == str(task_id):
                return True, queue_name, index
    return False, None, None


def seconds_from_progress(progress: dict[str, Any] | None) -> int | None:
    if not progress:
        return None
    estimated_at = parse_utc_iso(progress.get("estimated_completed_at") or progress.get("report_ready_at"))
    if estimated_at:
        return max(0, int((estimated_at - utc_now_naive()).total_seconds()))
    try:
        remaining = int(progress.get("remaining_seconds") or 0)
        if remaining > 0:
            return remaining
    except (TypeError, ValueError):
        pass
    return None


def queue_payload_plan(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "basic"
    return str(payload.get("plan_type") or payload.get("plan_type_used") or payload.get("plan") or "basic")


def queue_payload_estimated_seconds(payload: dict[str, Any] | None) -> int:
    if payload:
        try:
            target = int(payload.get("target_duration_seconds") or 0)
            if target > 0:
                return target
        except (TypeError, ValueError):
            pass
    return estimate_task_total_seconds(str((payload or {}).get("task_id") or ""), queue_payload_plan(payload))


def active_task_remaining_seconds(client: Any, exclude_task_id: str | None = None) -> int:
    total = 0
    for key in client.scan_iter("simulation:project:*:running", count=200):
        raw_task_id = client.get(redis_key_text(key))
        if not raw_task_id:
            continue
        task_id = queue_item_text(raw_task_id)
        if exclude_task_id and task_id == exclude_task_id:
            continue
        progress = redis_json_get(progress_key(task_id))
        if progress and str(progress.get("status") or "") not in {"running", "cancel_requested"}:
            continue
        remaining = seconds_from_progress(progress)
        total += remaining if remaining is not None else queue_payload_estimated_seconds(progress)
    return total


def queue_eta_for_task(client: Any, task_id: str | None, plan_type: str | None = None) -> dict[str, Any]:
    if not task_id:
        return {}
    seconds_before = active_task_remaining_seconds(client, exclude_task_id=task_id)
    found = False
    queued_ahead = 0
    for queue_name in QUEUE_NAMES:
        for raw_item in client.lrange(queue_name, 0, -1):
            payload = decode_queue_item(raw_item)
            if not payload:
                continue
            if str(payload.get("task_id")) == str(task_id):
                found = True
                current_seconds = queue_payload_estimated_seconds(payload)
                estimated_start_at = format_utc_iso(utc_now_naive() + timedelta(seconds=seconds_before))
                estimated_completed_at = format_utc_iso(utc_now_naive() + timedelta(seconds=seconds_before + current_seconds))
                return {
                    "queue_eta_seconds": seconds_before + current_seconds,
                    "estimated_start_at": estimated_start_at,
                    "estimated_completed_at": estimated_completed_at,
                    "remaining_seconds": seconds_before + current_seconds,
                    "queued_ahead_count": queued_ahead,
                }
            seconds_before += queue_payload_estimated_seconds(payload)
            queued_ahead += 1
    if found:
        return {}
    current_seconds = estimate_task_total_seconds(task_id, plan_type)
    return {
        "queue_eta_seconds": seconds_before + current_seconds,
        "estimated_start_at": format_utc_iso(utc_now_naive() + timedelta(seconds=seconds_before)),
        "estimated_completed_at": format_utc_iso(utc_now_naive() + timedelta(seconds=seconds_before + current_seconds)),
        "remaining_seconds": seconds_before + current_seconds,
        "queued_ahead_count": queued_ahead,
    }


def worker_heartbeat_snapshot(client: Any) -> dict[str, Any]:
    workers: list[dict[str, Any]] = []
    latest_seen_at: str | None = None
    for key in client.scan_iter("simulation:worker:*:heartbeat", count=200):
        key_text = redis_key_text(key)
        raw = client.get(key_text)
        payload: dict[str, Any]
        try:
            decoded = json.loads(queue_item_text(raw)) if raw else {}
            payload = decoded if isinstance(decoded, dict) else {"updated_at": queue_item_text(raw)}
        except json.JSONDecodeError:
            payload = {"updated_at": queue_item_text(raw)}
        worker_id = key_text.removeprefix("simulation:worker:").removesuffix(":heartbeat")
        updated_at = str(payload.get("updated_at") or payload.get("seen_at") or "")
        if updated_at and (latest_seen_at is None or updated_at > latest_seen_at):
            latest_seen_at = updated_at
        workers.append(
            {
                "worker_id": worker_id,
                "status": payload.get("status") or "unknown",
                "task_id": payload.get("task_id"),
                "project_id": payload.get("project_id"),
                "updated_at": updated_at or None,
            }
        )
    return {
        "worker_heartbeat_count": len(workers),
        "latest_worker_seen_at": latest_seen_at,
        "workers": workers,
    }


def build_queue_diagnostics(project: SimulationProject, progress: dict[str, Any] | None = None) -> dict[str, Any]:
    client = get_redis_client()
    task_id = project.task_id
    in_queue, queue_name, queue_position = find_task_in_queues(client, task_id)
    worker_snapshot = worker_heartbeat_snapshot(client)
    worker_online = bool(worker_snapshot["worker_heartbeat_count"])
    created_at = parse_utc_iso((progress or {}).get("created_at") or project.submitted_at)
    waiting_seconds = None
    if created_at:
        waiting_seconds = max(0, int((utc_now_naive() - created_at).total_seconds()))
    likely_stuck = bool(in_queue and not worker_online)
    if likely_stuck:
        message = "任务已提交，系统正在等待处理资源恢复"
    elif in_queue:
        message = "任务已提交，系统会按顺序自动开始"
    elif str((progress or {}).get("status")) == "running":
        message = "任务已进入生成阶段"
    elif project.status == REPORT_WAITING_STATUS:
        message = "报告数据已生成，正在整理最终展示"
    else:
        message = "当前任务未处于等待队列"
    eta_payload = queue_eta_for_task(client, task_id, project.plan_type_used) if in_queue else {}
    if project.status == REPORT_WAITING_STATUS:
        wait_extra = report_wait_progress_extra(project.result_data or {})
        eta_payload = {
            "queue_eta_seconds": wait_extra.get("remaining_seconds"),
            "estimated_start_at": format_utc_iso(project.started_at) if project.started_at else wait_extra.get("report_wait_started_at"),
            "estimated_completed_at": wait_extra.get("estimated_completed_at"),
            "remaining_seconds": wait_extra.get("remaining_seconds"),
            "queued_ahead_count": 0,
        }
    return {
        "task_id": task_id,
        "in_queue": in_queue,
        "queue_name": queue_name,
        "queue_position": queue_position,
        "waiting_seconds": waiting_seconds,
        "worker_online": worker_online,
        "likely_stuck": likely_stuck,
        "message": message,
        **eta_payload,
        **worker_snapshot,
    }


def task_log_to_dict(item: SimulationTaskLog) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "task_id": item.task_id,
        "snapshot_id": item.snapshot_id,
        "timestamp": item.timestamp,
        "stage": item.stage,
        "log_level": item.log_level,
        "message": item.message,
        "detail_json": item.detail_json or {},
        "created_at": item.created_at,
    }


def build_rag_search_text(product_definition: dict[str, Any], market_config: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("product_name", "name", "brand", "major_category", "sub_category", "category", "subcategory", "price_cny"):
        value = product_definition.get(key)
        if value:
            parts.append(str(value))
    specs = product_definition.get("specifications")
    if isinstance(specs, dict):
        for key, value in specs.items():
            if value is not None and value != "":
                parts.append(f"{key}:{value}")
    for key in ("target_crowd", "scene", "price_band"):
        value = market_config.get(key)
        if value:
            parts.append(str(value))
    scenes = market_config.get("scenes")
    if isinstance(scenes, list):
        parts.extend(str(item) for item in scenes if item)
    strategy_text = market_strategy_text(market_config)
    if strategy_text:
        parts.append(strategy_text)
    profile_text = crowd_profile_text(market_config)
    if profile_text:
        parts.append(profile_text)
    return " ".join(parts)[:2000]


def build_rag_queries(product_definition: dict[str, Any], market_config: dict[str, Any]) -> dict[str, str]:
    legacy_text = build_rag_search_text(product_definition, market_config)
    product_name = product_definition.get("product_name") or product_definition.get("name") or "产品"
    category = product_definition.get("subcategory") or product_definition.get("category") or ""
    brand = product_definition.get("brand") or ""
    target = market_config.get("target_crowd") or market_config.get("crowd") or ""
    strategy = market_strategy_text(market_config)
    scenes = market_config.get("scenes")
    scene = "；".join(str(item) for item in scenes if item) if isinstance(scenes, list) else (market_config.get("scene") or "")
    profile_text = crowd_profile_text(market_config)
    return {
        "product_query": f"{legacy_text} {brand} {product_name} 功能 参数 价格".strip()[:2000],
        "competitor_query": f"{legacy_text} {category} {brand} {product_name} 竞品 对比 价格 规格".strip()[:2000],
        "market_query": f"{category} {product_name} {target} {profile_text} {strategy} {scene} 人群 场景 渠道 营销".strip()[:2000],
    }


def make_config_snapshot(
    project: SimulationProject,
    user: User,
    product_definition: dict[str, Any],
    market_config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    sample_size = market_config.get("sample_size") or (10000 if (project.plan_type_used or "basic") == "pro" else 1000)
    social_network = {
        "enabled": settings.social_network_enabled,
        "topology": "connected_watts_strogatz",
        "k": settings.social_network_k,
        "rewire_probability": settings.social_network_rewire_probability,
        "max_rounds": settings.social_network_max_rounds,
        "convergence_threshold": settings.social_network_convergence_threshold,
        "trust_sensitivity_min": settings.social_trust_sensitivity_min,
        "trust_sensitivity_max": settings.social_trust_sensitivity_max,
        "representative_ratio": settings.social_representative_ratio,
        "representative_min": settings.social_representative_min,
        "representative_max": settings.social_representative_max,
    }
    social_network["representative_agent_count"] = representative_agent_count(sample_size, social_network)
    market_assumptions = market_config.get("market_assumptions") if isinstance(market_config.get("market_assumptions"), dict) else {}
    market_assumptions = {
        "assumed_market_competitor_count": max(5, min(50, int(positive_int(market_assumptions.get("assumed_market_competitor_count")) or 20))),
        "market_anchor": market_assumptions.get("market_anchor") if isinstance(market_assumptions.get("market_anchor"), dict) else None,
    }
    configured_profile = market_config.get("decision_weight_profile") if isinstance(market_config.get("decision_weight_profile"), dict) else {}
    weight_profile = decision_weight_profile({"decision_weight_profile": configured_profile})
    propagation_config = market_config.get("social_propagation_config") if isinstance(market_config.get("social_propagation_config"), dict) else {}
    simulation_params = {
        "simulation_version": "v0.2",
        "sample_size": sample_size,
        "random_seed": project.id,
        "enable_rag": settings.enable_rag,
        "enable_distill_check": settings.enable_distill_check,
        "rag_top_k": settings.rag_top_k,
        "distill_sample_size": market_config.get("distill_sample_size") or 100,
        "distill_consistency_threshold": market_config.get("distill_consistency_threshold") or 0.8,
        "social_network": social_network,
    }
    rag_queries = build_rag_queries(product_definition, market_config)
    legacy_text = build_rag_search_text(product_definition, market_config)
    hash_basis = {
        "project_id": project.id,
        "user_id": user.id,
        "project_name": project.project_name,
        "plan_type_used": project.plan_type_used or "basic",
        "product_definition": product_definition,
        "market_config": market_config,
        "market_assumptions": market_assumptions,
        "decision_weight_profile": weight_profile,
        "social_propagation_config": propagation_config,
        "commercial_model_version": COMMERCIAL_MODEL_VERSION,
        "simulation_params": simulation_params,
        "rag_queries": rag_queries,
    }
    raw = json.dumps(hash_basis, ensure_ascii=False, sort_keys=True, default=str)
    snapshot_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    snapshot = {
        **hash_basis,
        "snapshot_id": f"snap_{project.id}_{snapshot_hash[:12]}",
        "snapshot_hash": snapshot_hash,
        "submitted_at": utc_now_iso(),
        "rag_search_text": legacy_text,
        "rag_search_text_legacy": legacy_text,
        "rag_search_queries": rag_queries,
        "simulation_version": simulation_params["simulation_version"],
    }
    return snapshot, snapshot_hash


def get_owned_project(db: Session, user: User, project_id: int) -> SimulationProject:
    project = db.scalar(
        select(SimulationProject)
        .options(
            defer(SimulationProject.config_snapshot),
            defer(SimulationProject.result_data),
        )
        .where(
            SimulationProject.id == project_id,
            SimulationProject.user_id == user.id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def ensure_draft_version(project: SimulationProject, draft_version: int | None) -> None:
    if draft_version is not None and draft_version != project.draft_version:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_CONFLICT",
                "message": "当前草稿已在其他页面被修改，请刷新后再继续编辑",
                "data": {"server_draft_version": project.draft_version},
            },
        )


def get_owned_export_task(db: Session, user: User, export_task_id: int) -> ExportTask:
    task = db.scalar(
        select(ExportTask).where(
            ExportTask.id == export_task_id,
            ExportTask.user_id == user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="导出任务不存在")
    return task


def queue_name_for_user(user: User) -> str:
    return settings.redis_pro_queue if user.plan_type == "pro" else settings.redis_basic_queue


def queue_name_for_plan(plan_type: str | None) -> str:
    return settings.redis_pro_queue if plan_type == "pro" else settings.redis_basic_queue


def charge_quota_if_needed(db: Session, user: User, project: SimulationProject, task_id: str) -> None:
    if project.plan_type_used == "pro" or project.quota_charged:
        return
    if user.basic_quota_remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail={"code": "QUOTA_EXCEEDED", "message": "普通版仿真次数不足", "data": {}},
        )
    user.basic_quota_remaining -= 1
    project.quota_charged = True
    db.add(
        QuotaLog(
            user_id=user.id,
            project_id=project.id,
            task_id=task_id,
            change_type="charge",
            change_amount=-1,
            reason="启动仿真任务扣减普通版次数",
        )
    )


def enabled_param_count(product_definition: dict[str, Any]) -> int:
    params = product_definition.get("params")
    if isinstance(params, list):
        return sum(1 for item in params if isinstance(item, dict) and item.get("enabled", True))
    specs = product_definition.get("specifications")
    if isinstance(specs, dict):
        return len([key for key, value in specs.items() if value not in (None, "")])
    return 0


def product_text_field(product_definition: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = product_definition.get(key)
        if value is not None:
            text_value = str(value).strip()
            if text_value:
                return text_value
    return ""


def validate_step1_product_definition(product_definition: dict[str, Any]) -> None:
    product_name = product_text_field(product_definition, "product_name", "name")
    category = product_text_field(product_definition, "category", "major_category")
    subcategory = product_text_field(product_definition, "subcategory", "sub_category", "template_subcategory")
    if not product_name:
        raise HTTPException(
            status_code=422,
            detail={"code": "STEP1_REQUIRED_FIELD_MISSING", "message": "请先填写产品名称", "data": {"field": "product_name"}},
        )
    if not category:
        raise HTTPException(
            status_code=422,
            detail={"code": "STEP1_REQUIRED_FIELD_MISSING", "message": "请先选择产品大品类", "data": {"field": "category"}},
        )
    if not subcategory:
        raise HTTPException(
            status_code=422,
            detail={"code": "STEP1_REQUIRED_FIELD_MISSING", "message": "请先选择或填写产品小品类", "data": {"field": "subcategory"}},
        )
    raw_price = product_definition.get("price_cny") or product_definition.get("price") or product_definition.get("reference_price")
    try:
        price = float(str(raw_price).replace(",", "").strip()) if raw_price is not None else 0
    except (TypeError, ValueError):
        price = 0
    if price <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "STEP1_REQUIRED_FIELD_MISSING",
                "message": "请填写产品价格，价格需为确定数字，例如 3999",
                "data": {"field": "price_cny"},
            },
        )
    product_definition["price_cny"] = price


def competitor_count(market_config: dict[str, Any]) -> int:
    competitors = normalize_market_competitors(market_config).get("competitors")
    if isinstance(competitors, list):
        return len(competitors)
    return 1 if market_config.get("basic_competitor") else 0


def _competitor_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("product_name", "name", "display_name", "confirmed_sku", "title"):
        raw = value.get(key)
        if raw:
            return str(raw).strip()
    return ""


def normalize_market_competitors(market_config: dict[str, Any] | None) -> dict[str, Any]:
    market = dict(market_config or {})
    competitors = market.get("competitors")
    if not isinstance(competitors, list):
        return market
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(competitors):
        if not isinstance(item, dict):
            continue
        name = _competitor_name(item)
        if not name:
            continue
        copied = dict(item)
        copied["product_name"] = name
        if not copied.get("id"):
            copied["id"] = -(index + 1)
        key = (str(copied.get("id", "")), name)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(copied)
    market["competitors"] = normalized
    return market


def _strategy_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "strategy", "title", "label"):
            raw = value.get(key)
            if raw:
                return str(raw).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _scene_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "scene", "title", "label"):
            raw = value.get(key)
            if raw:
                return str(raw).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def canonicalize_market_config(market_config: dict[str, Any] | None) -> dict[str, Any]:
    market = canonicalize_market_crowds(normalize_market_competitors(market_config))
    raw_scenes = market.get("scenes")
    scenes: list[str] = []
    if isinstance(raw_scenes, list):
        for item in raw_scenes:
            name = _scene_name(item)
            if name and name not in scenes:
                scenes.append(name)
    else:
        name = _scene_name(market.get("scene") or market.get("basic_selected_scene"))
        if name:
            scenes.append(name)
    if scenes:
        market["scenes"] = scenes
        market["scene"] = scenes[0]
        scene_details = _dict_value(market.get("scene_details"))
        legacy_scene_detail = _dict_value(market.get("scene_detail"))
        if legacy_scene_detail and scenes[0] not in scene_details:
            scene_details[scenes[0]] = legacy_scene_detail
        if scene_details:
            market["scene_details"] = scene_details
            market["scene_detail"] = _dict_value(scene_details.get(scenes[0])) or legacy_scene_detail
    raw_strategies = market.get("strategies")
    strategies: list[Any] = []
    if isinstance(raw_strategies, list):
        for item in raw_strategies:
            name = _strategy_name(item)
            if not name:
                continue
            if isinstance(item, dict):
                copied = dict(item)
                copied["name"] = name
                strategies.append(copied)
            else:
                strategies.append(name)
    else:
        name = _strategy_name(market.get("strategy") or market.get("basic_selected_strategy"))
        if name:
            strategies.append(name)
    if strategies:
        market["strategies"] = strategies
        market["strategy"] = _strategy_name(strategies[0])
    return market


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _has_report_value(value: Any) -> bool:
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return value not in (None, "")


def _number_value(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return default
    return default


def _positive_number_value(value: Any) -> float | None:
    parsed = _number_value(value, -1)
    return parsed if parsed > 0 else None


def _project_price_cny_for_report(
    project: SimulationProject,
    result_data: dict[str, Any],
    product_definition: dict[str, Any],
) -> float | None:
    snapshot_product = _dict_value(_dict_value(project.config_snapshot).get("product_definition"))
    result_product = _dict_value(result_data.get("product_definition")) or _dict_value(result_data.get("product"))
    project_product = _dict_value(project.product_definition)
    for value in (
        snapshot_product.get("price_cny"),
        product_definition.get("price_cny"),
        result_product.get("price_cny"),
        project_product.get("price_cny"),
        snapshot_product.get("price"),
        result_product.get("price"),
        project_product.get("price"),
    ):
        parsed = _positive_number_value(value)
        if parsed is not None:
            return parsed
    return None


def _snapshot_for_report_repair(project: SimulationProject, result_data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    snapshot = _dict_value(project.config_snapshot)
    if snapshot.get("product_definition") or snapshot.get("market_config"):
        return snapshot, "config_snapshot"

    product_definition = (
        _dict_value(result_data.get("product_definition"))
        or _dict_value(result_data.get("product"))
        or _dict_value(project.product_definition)
    )
    market_config = (
        _dict_value(result_data.get("market_config"))
        or _dict_value(result_data.get("market"))
        or _dict_value(project.market_config)
    )
    return (
        {
            "snapshot_id": result_data.get("snapshot_id") or project.snapshot_hash or f"project_{project.id}",
            "snapshot_hash": result_data.get("snapshot_hash") or project.snapshot_hash,
            "product_definition": product_definition,
            "market_config": canonicalize_market_config(market_config),
        },
        "project_current_fallback",
    )


def _evidence_for_report_repair(result_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    for key in ("rag_evidence", "final_rag_evidence", "evidence"):
        value = result_data.get(key)
        if isinstance(value, dict):
            return {
                str(item_key): [item for item in _list_value(items) if isinstance(item, dict)]
                for item_key, items in value.items()
            }
    rows = [item for item in _list_value(result_data.get("evidence_used")) if isinstance(item, dict)]
    return {"evidence_used": rows} if rows else {}


def _segments_for_report_repair(market_config: dict[str, Any]) -> list[dict[str, Any]]:
    market = canonicalize_market_crowds(market_config)
    raw_segments = _list_value(market.get("crowd_segments"))
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw_segments, 1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("segment") or "").strip()
        if not name:
            continue
        ratio = _number_value(item.get("ratio"), 0)
        profile = _dict_value(item.get("profile")) or _dict_value(item.get("crowd_profile"))
        rows.append(
            {
                "name": name,
                "ratio": ratio if ratio > 0 else round(100 / max(1, len(raw_segments)), 1),
                "profile": profile,
                "crowd_profile": profile,
                "is_custom": bool(item.get("is_custom")),
            }
        )
    if rows:
        return rows
    fallback_name = str(market.get("target_crowd") or market.get("basic_target_crowd") or "").strip()
    if fallback_name:
        profile = _dict_value(market.get("crowd_profile"))
        return [{"name": fallback_name, "ratio": 100, "profile": profile, "crowd_profile": profile, "is_custom": False}]
    return []


def _aggregation_for_report_repair(
    result_data: dict[str, Any],
    market_config: dict[str, Any],
    chart_data: dict[str, Any],
) -> dict[str, Any]:
    aggregation = dict(_dict_value(result_data.get("aggregation")))
    if "purchase_intent_avg" not in aggregation:
        values: list[float] = []
        for item in _list_value(result_data.get("purchase_decisions")):
            if not isinstance(item, dict):
                continue
            raw = item.get("purchase_intent") or item.get("purchase_intent_score") or item.get("intent") or item.get("score")
            parsed = _number_value(raw, -1)
            if parsed >= 0:
                values.append(parsed / 100 if parsed > 1 else parsed)
        if values:
            aggregation["purchase_intent_avg"] = sum(values) / len(values)
        else:
            overview = _dict_value(chart_data.get("overview_metrics"))
            aggregation["purchase_intent_avg"] = _number_value(overview.get("purchase_intent_index"), 55) / 100

    configured_segments = _segments_for_report_repair(market_config)
    existing_summary = aggregation.get("segment_summary")
    if not isinstance(existing_summary, dict) or len(existing_summary) < len(configured_segments):
        avg = max(0.0, min(1.0, _number_value(aggregation.get("purchase_intent_avg"), 0.55)))
        segment_summary: dict[str, Any] = {}
        for segment in configured_segments:
            ratio = _number_value(segment.get("ratio"), 100)
            segment_summary[str(segment.get("name") or "目标人群")] = {
                "avg_purchase_intent": avg,
                "count": 0,
                "ratio": ratio,
                "weighted_contribution": avg * ratio / 100,
            }
        if segment_summary:
            aggregation["segment_summary"] = segment_summary

    evidence_quality = _dict_value(aggregation.get("evidence_quality"))
    if "price_coverage_pct" not in evidence_quality:
        competitors = _list_value(market_config.get("competitors"))
        named = [item for item in competitors if isinstance(item, dict) and _competitor_name(item)]
        priced = [
            item
            for item in named
            if _number_value(item.get("price") or item.get("price_cny"), -1) > 0
        ]
        evidence_quality["price_coverage_pct"] = round(len(priced) / max(1, len(named)) * 100, 1) if named else 0
    aggregation["evidence_quality"] = evidence_quality
    return aggregation


def repair_project_report_data(db: Session, project: SimulationProject) -> bool:
    result_data = dict(_dict_value(project.result_data))
    if not result_data:
        return False

    chart_data = dict(_dict_value(result_data.get("chart_data")))
    snapshot, source = _snapshot_for_report_repair(project, result_data)
    product_definition = _dict_value(snapshot.get("product_definition"))
    market_config = canonicalize_market_config(_dict_value(snapshot.get("market_config")))
    product_price = _project_price_cny_for_report(project, result_data, product_definition)
    if product_price is not None:
        product_definition = {**product_definition, "price_cny": product_price}
    snapshot["product_definition"] = product_definition
    snapshot["market_config"] = market_config
    evidence = _evidence_for_report_repair(result_data)
    aggregation = _aggregation_for_report_repair(result_data, market_config, chart_data)
    agents = [item for item in _list_value(result_data.get("agent_samples")) if isinstance(item, dict)]
    decisions = [item for item in _list_value(result_data.get("purchase_decisions")) if isinstance(item, dict)]
    plan_type = "pro" if str(project.plan_type_used or result_data.get("plan_type_used") or chart_data.get("plan_type")) == "pro" else "basic"

    generated = build_chart_data(snapshot, evidence, agents, decisions, aggregation, plan_type=plan_type)
    changed = False
    for key, value in generated.items():
        if _has_report_value(value) and not _has_report_value(chart_data.get(key)):
            chart_data[key] = value
            changed = True

    for key in (
        "market_share_scope",
        "market_share_scenarios",
        "data_gaps",
        "commercial_model_version",
        "strategy_economics",
        "differentiation_audit",
        "simulation_boundaries",
    ):
        if _has_report_value(generated.get(key)) and not _has_report_value(result_data.get(key)):
            result_data[key] = generated[key]
            changed = True
    if decisions and not _has_report_value(result_data.get("channel_scenarios")):
        decision_summary = build_decision_model_summary(decisions, snapshot)
        result_data["channel_scenarios"] = decision_summary.get("channel_scenarios", [])
        result_data.setdefault("decision_model", decision_summary)
        changed = True
    if decisions and not _has_report_value(result_data.get("propagation_funnel")):
        social = _dict_value(result_data.get("social_simulation"))
        result_data["propagation_funnel"] = build_propagation_funnel(snapshot, agents, decisions, social)
        changed = True

    segments = _segments_for_report_repair(market_config)
    if segments and not _has_report_value(result_data.get("crowd_segments")):
        result_data["crowd_segments"] = segments
        changed = True
    if segments and not _has_report_value(result_data.get("target_segments")):
        result_data["target_segments"] = [
            {
                "name": item["name"],
                "ratio": item.get("ratio", 100),
                "crowd_profile": item.get("crowd_profile") or item.get("profile") or {},
                "insight": f"{item['name']} 占比 {item.get('ratio', 100)}%，作为本轮仿真的目标客群之一。",
            }
            for item in segments
        ]
        changed = True

    if product_definition and not _has_report_value(result_data.get("product_definition")):
        result_data["product_definition"] = product_definition
        changed = True
    elif product_price is not None:
        result_product = dict(_dict_value(result_data.get("product_definition")))
        if _positive_number_value(result_product.get("price_cny")) is None:
            result_product.update(product_definition)
            result_product["price_cny"] = product_price
            result_data["product_definition"] = result_product
            changed = True
    if product_price is not None:
        pricing = dict(_dict_value(result_data.get("pricing_analysis")))
        if _positive_number_value(pricing.get("reference_price")) is None:
            pricing["reference_price"] = product_price
            result_data["pricing_analysis"] = pricing
            changed = True
    if market_config and not _has_report_value(result_data.get("market_config")):
        result_data["market_config"] = market_config
        changed = True
    if aggregation and aggregation != result_data.get("aggregation"):
        result_data["aggregation"] = aggregation
        changed = True
    if chart_data != result_data.get("chart_data"):
        result_data["chart_data"] = chart_data
        changed = True

    if changed:
        runtime = _dict_value(result_data.get("_runtime"))
        repairs = _list_value(runtime.get("chart_repairs"))
        repairs.append({"source": source, "repaired_at": utc_now_iso()})
        runtime["chart_repairs"] = repairs[-5:]
        result_data["_runtime"] = runtime
        project.result_data = result_data
        db.add(project)
        db.commit()
        db.refresh(project)
    return changed


def market_strategy_text(market_config: dict[str, Any] | None) -> str:
    market = canonicalize_market_config(market_config)
    names = [_strategy_name(item) for item in market.get("strategies", []) if _strategy_name(item)]
    if not names:
        fallback = _strategy_name(market.get("strategy") or market.get("basic_selected_strategy"))
        names = [fallback] if fallback else []
    return "；".join(dict.fromkeys(names))


def validate_market_crowds(market_config: dict[str, Any], plan_type: str) -> dict[str, Any]:
    segments, error_code = validate_crowd_segments(market_config)
    if error_code:
        messages = {
            "CROWD_RATIO_INVALID": "目标客群名称不可重复，且每类客群比例必须为正整数",
            "CROWD_RATIO_TOTAL_INVALID": "目标客群比例合计必须为 100%",
        }
        raise HTTPException(
            status_code=422,
            detail={"code": error_code, "message": messages[error_code], "data": {}},
        )
    if plan_type == "basic" and len(segments) > 3:
        raise HTTPException(
            status_code=403,
            detail={"code": "BASIC_CROWD_LIMIT", "message": "普通版最多选择 3 类目标客群", "data": {}},
        )
    if not segments:
        return canonicalize_market_config(market_config)
    return canonicalize_market_config({**market_config, "crowd_segments": segments})


def normalize_basic_config(
    product_definition: dict[str, Any],
    market_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    product = dict(product_definition)
    market = canonicalize_market_config(market_config)
    params = product.get("params")
    if isinstance(params, list):
        enabled_seen = 0
        normalized_params = []
        for item in params:
            if not isinstance(item, dict):
                continue
            copied = dict(item)
            if copied.get("enabled", True):
                enabled_seen += 1
                copied["enabled"] = enabled_seen <= 3
            copied.pop("weight", None)
            normalized_params.append(copied)
        product["params"] = normalized_params
    market["sample_size"] = 1000
    if isinstance(market.get("competitors"), list):
        market["competitors"] = market["competitors"][:1]
    if isinstance(market.get("strategies"), list):
        market["strategies"] = market["strategies"][:1]
        if market["strategies"]:
            market["strategy"] = _strategy_name(market["strategies"][0])
    if isinstance(market.get("scenes"), list):
        market["scenes"] = market["scenes"][:1]
        if market["scenes"]:
            market["scene"] = _scene_name(market["scenes"][0])
    return product, market


def validate_version_limits(project: SimulationProject, product_definition: dict[str, Any], market_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_type = project.plan_type_used or "basic"
    market_config = validate_market_crowds(market_config, plan_type)
    if plan_type == "pro":
        return product_definition, market_config
    if enabled_param_count(product_definition) > 3:
        raise HTTPException(
            status_code=403,
            detail={"code": "BASIC_PARAM_LIMIT", "message": "普通版最多启用 3 个产品参数", "data": {}},
        )
    if competitor_count(market_config) > 1:
        raise HTTPException(
            status_code=403,
            detail={"code": "BASIC_COMPETITOR_LIMIT", "message": "普通版最多选择 1 个竞品", "data": {}},
        )
    return normalize_basic_config(product_definition, market_config)


@app.get("/health")
def health(db: DbSession) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["mysql"] = {"ok": True}
    except Exception as exc:
        checks["mysql"] = {"ok": False, "message": str(exc)}

    try:
        pong = get_redis_client().ping()
        checks["redis"] = {"ok": bool(pong)}
    except Exception as exc:
        checks["redis"] = {"ok": False, "message": str(exc)}

    try:
        checks["faiss"] = {"ok": True, **get_rag_service().status()}
    except Exception as exc:
        checks["faiss"] = {"ok": False, "message": str(exc)}

    checks["distill"] = {
        "enabled": settings.enable_distill_check,
        "model_path": settings.distill_model_path,
        "api_base_configured": bool(settings.distill_api_base),
        "consistency_path": settings.distill_consistency_path,
        "model_version": settings.distill_model_version,
        "batch_size": settings.distill_batch_size,
    }
    checks["public_evidence"] = {
        "enabled": settings.public_evidence_enabled,
        "provider": settings.public_evidence_provider,
        "api_base_configured": bool(settings.public_evidence_api_base),
        "api_key_configured": bool(settings.public_evidence_api_key or settings.price_enrichment_api_key or settings.embedding_api_key),
        "model": settings.public_evidence_model,
        "basic_query_limit": settings.public_evidence_basic_query_limit,
        "pro_query_limit": settings.public_evidence_pro_query_limit,
    }
    ok = checks["mysql"]["ok"] and checks["redis"]["ok"] and checks["faiss"]["ok"]
    return {
        "ok": ok,
        "app": settings.app_name,
        "env": settings.app_env,
        "time": utc_now_iso(),
        "checks": checks,
    }


@app.get("/api/categories")
def list_categories(
    db: DbSession,
    active_only: bool = True,
) -> dict[str, Any]:
    stmt = select(ProductCategory)
    if active_only:
        stmt = stmt.where(ProductCategory.is_active.is_(True))
    stmt = stmt.order_by(ProductCategory.sort_order, ProductCategory.id)
    items = [category_to_dict(row) for row in db.scalars(stmt)]
    return {"total": len(items), "items": items}


@app.get("/api/categories/{category_id}/fields")
def list_category_fields(category_id: int, db: DbSession) -> dict[str, Any]:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="品类不存在")

    stmt = (
        select(ProductFieldTemplate)
        .where(ProductFieldTemplate.category_id == category_id)
        .order_by(ProductFieldTemplate.sort_order, ProductFieldTemplate.id)
    )
    items = [field_to_dict(row, category) for row in db.scalars(stmt)]
    return {"category": category_to_dict(category), "total": len(items), "items": items}


@app.get("/api/products")
def list_products(
    background_tasks: BackgroundTasks,
    db: DbSession,
    category_id: int | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    brand: str | None = None,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = [Product.is_active.is_(True)]
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if category:
        filters.append(Product.category == category)
    if subcategory:
        filters.append(Product.subcategory == subcategory)
    if brand:
        filters.append(Product.brand == brand)
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Product.product_name.like(pattern),
                Product.brand.like(pattern),
                Product.confirmed_sku.like(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    stmt = (
        select(Product)
        .where(*filters)
        .order_by(Product.id)
        .offset(offset)
        .limit(limit)
    )
    rows = list(db.scalars(stmt))
    missing_price_ids = [
        row.id
        for row in rows
        if row.price_cny is None and (row.product_name or row.confirmed_sku)
    ]
    queued_count = enqueue_product_price_enrichment(background_tasks, missing_price_ids)
    return {
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "items": [product_to_dict(row) for row in rows],
        "price_enrichment": {
            "enabled": settings.price_enrichment_enabled,
            "queued": queued_count,
        },
    }


@app.get("/api/products/{product_id}")
def get_product(product_id: int, db: DbSession) -> dict[str, Any]:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product_to_dict(product)


@app.get("/api/market/crowd-templates")
def list_crowd_templates(db: DbSession) -> dict[str, Any]:
    stmt = (
        select(MarketCrowdTemplate)
        .where(MarketCrowdTemplate.is_active.is_(True))
        .order_by(MarketCrowdTemplate.sort_order, MarketCrowdTemplate.id)
    )
    items = [crowd_to_dict(row) for row in db.scalars(stmt)]
    return {"total": len(items), "items": items}


@app.get("/api/market/strategy-templates")
def list_strategy_templates(db: DbSession) -> dict[str, Any]:
    stmt = (
        select(MarketStrategyTemplate)
        .where(MarketStrategyTemplate.is_active.is_(True))
        .order_by(MarketStrategyTemplate.sort_order, MarketStrategyTemplate.id)
    )
    items = [strategy_to_dict(row) for row in db.scalars(stmt)]
    return {"total": len(items), "items": items}


@app.get("/api/market/scene-templates")
def list_scene_templates(db: DbSession) -> dict[str, Any]:
    stmt = (
        select(MarketSceneTemplate)
        .where(MarketSceneTemplate.is_active.is_(True))
        .order_by(MarketSceneTemplate.sort_order, MarketSceneTemplate.id)
    )
    items = [scene_to_dict(row) for row in db.scalars(stmt)]
    return {"total": len(items), "items": items}


@app.get("/api/market/templates")
def list_market_templates(db: DbSession) -> dict[str, Any]:
    return {
        "crowd": list_crowd_templates(db),
        "strategy": list_strategy_templates(db),
        "scene": list_scene_templates(db),
    }


def assistant_route_fallback(payload: AssistantChatRequest, reason: str | None = None) -> dict[str, Any]:
    message = (payload.message or "").strip()
    reply = (
        "助手已切换为本地说明，页面填写和保存不受影响。"
        "您可以继续填写；如果是字段填写问题，请优先按页面必填提示完成产品价格、目标客群、场景、策略和竞品信息。"
    )
    if any(keyword in message.lower() for keyword in ("roi", "投入产出", "回报")):
        reply = (
            "ROI 可以理解为本次策略的投入产出参考值。数值越高，说明在当前产品、人群和价格配置下，"
            "该策略更可能带来有效转化。建议您结合策略触达渠道、预算强度和执行动作一起判断。"
        )
    elif "价格" in message:
        reply = (
            "价格请填写贵公司主推热销款产品的实际售价，仅填写数字，例如 3999。"
            "系统会用这个确定单价计算购买力、价格敏感曲线和竞品价格覆盖情况。"
        )
    elif "竞品" in message:
        reply = (
            "竞品用于判断贵公司产品相对同类产品的价格、卖点和参数位置。"
            "建议至少填写或选择 1 个有名称的竞品；价格缺失不影响保存，系统会优先用数据库和公开资料补全。"
        )
    elif any(keyword in message for keyword in ("产品怎么样", "我们的产品", "这个产品", "好不好", "产品建议", "优缺点", "优势", "短板")):
        reply = (
            "贵公司的产品建议从人群匹配、价格接受度、核心参数和竞品差异四个角度判断。"
            "如果 Step1 的价格和核心参数、Step2 的客群、场景、策略和竞品都已填写，报告会结合这些信息给出购买意愿、价格敏感和策略 ROI。"
            "建议您优先查看 Step4 的总览、竞品分析和策略分析，不要只用单一指标判断产品好坏。"
        )
    elif "没有图" in message or "暂无数据" in message or "缺" in message:
        reply = (
            "报告图表通常依赖 Step1 的价格和核心参数、Step2 的人群比例、场景、策略和竞品。"
            "如果这些都已填写但图表仍缺失，系统会尝试自动修复报告数据；竞品资料覆盖较少时可联系客服 18960333566 补充资料。"
        )
    if reason:
        logger.warning("assistant_route_fallback", extra={"reason": reason, "project_id": payload.project_id})
    return {
        "reply": reply,
        "quick_replies": ["价格应该怎么填？", "竞品怎么选？", "ROI 是什么？"],
        "field_cards": [],
        "source": "local_fallback",
    }


@app.post("/api/assistant/chat")
def assistant_chat(
    payload: AssistantChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    try:
        project = get_owned_project(db, current_user, payload.project_id)
        return build_assistant_response(db, project, payload)
    except Exception as exc:
        logger.exception("assistant_chat_failed")
        return assistant_route_fallback(payload, reason=exc.__class__.__name__)


def ensure_debug_enabled() -> None:
    if not settings.enable_debug_api:
        raise HTTPException(status_code=404, detail="调试接口未开启")


@app.get("/api/debug/faiss/status")
def debug_faiss_status() -> dict[str, Any]:
    ensure_debug_enabled()
    return get_rag_service().status()


@app.get("/api/debug/pdf/status")
def debug_pdf_status() -> dict[str, Any]:
    ensure_debug_enabled()
    return check_pdf_render_prerequisites()


@app.post("/api/debug/rag/search")
def debug_rag_search(payload: RagSearchRequest, db: DbSession) -> dict[str, Any]:
    ensure_debug_enabled()
    try:
        evidence = get_rag_service().search(
            payload.query,
            top_k=payload.top_k,
            source_include=payload.source_include,
            source_exclude=payload.source_exclude,
            candidate_k=payload.candidate_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAG 检索失败：{exc}") from exc
    product_items: list[dict[str, Any]] = []
    if payload.include_products:
        product_items = search_product_evidence(
            db,
            payload.product_definition or {},
            payload.query,
            top_k=payload.top_k,
        )
    return {
        "query": payload.query,
        "top_k": payload.top_k,
        "items": [*product_items, *evidence],
        "product_items": product_items,
        "faiss_items": evidence,
    }


@app.post("/api/debug/distill/check")
def debug_distill_check(payload: DistillDebugRequest) -> dict[str, Any]:
    ensure_debug_enabled()
    return run_debug_distill_check(
        payload.snapshot,
        payload.agents,
        payload.purchase_decisions,
        threshold=payload.threshold,
        sample_size=payload.sample_size,
        validation_batch_id=payload.validation_batch_id,
    )


@app.get("/api/debug/queue/status")
def debug_queue_status() -> dict[str, Any]:
    ensure_debug_enabled()
    client = get_redis_client()
    queues = {
        "default": settings.redis_task_queue,
        "basic": settings.redis_basic_queue,
        "pro": settings.redis_pro_queue,
        "export": settings.redis_export_queue,
    }
    lengths = {name: client.llen(queue) for name, queue in queues.items()}
    progress_count = sum(1 for _ in client.scan_iter("simulation:progress:*", count=200))
    task_heartbeat_count = sum(1 for _ in client.scan_iter("simulation:heartbeat:*", count=200))
    lock_count = sum(1 for _ in client.scan_iter("simulation:project:*:running", count=200))
    worker_snapshot = worker_heartbeat_snapshot(client)
    return {
        "queues": queues,
        "lengths": lengths,
        "progress_count": progress_count,
        "heartbeat_count": task_heartbeat_count,
        "task_heartbeat_count": task_heartbeat_count,
        **worker_snapshot,
        "project_lock_count": lock_count,
        "heavy_resource_locked": bool(client.get("simulation:heavy-resource:lock")),
    }


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> dict[str, Any]:
    username = payload.username.strip()
    email = payload.email.strip() if payload.email else None
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    if email and db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="邮箱已存在")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_to_dict(user)}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: DbSession) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.username == payload.username.strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.last_login_at = utc_now_naive()
    db.commit()
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_to_dict(user)}


@app.get("/api/auth/me")
def me(current_user: CurrentUser) -> dict[str, Any]:
    return user_to_dict(current_user)


@app.get("/api/user/profile")
def get_user_profile(current_user: CurrentUser) -> dict[str, Any]:
    return user_to_dict(current_user)


@app.put("/api/user/profile")
def update_user_profile(
    payload: UpdateUserProfileRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    if payload.email is not None:
        email = payload.email.strip() or None
        if email:
            exists = db.scalar(select(User).where(User.email == email, User.id != current_user.id))
            if exists:
                raise HTTPException(status_code=409, detail="邮箱已存在")
        current_user.email = email
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url.strip() or None
    db.commit()
    db.refresh(current_user)
    return user_to_dict(current_user)


AVATAR_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
AVATAR_MAX_BYTES = 2 * 1024 * 1024


def avatar_upload_dir() -> Path:
    return settings.resolve_path(settings.export_dir) / "uploads" / "avatars"


def avatar_media_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


@app.get("/api/user/avatar/default")
def default_user_avatar() -> FileResponse:
    path = settings.resolve_path("avatar.jpg")
    if not path.exists():
        raise HTTPException(status_code=404, detail="默认头像不存在")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/user/avatar/files/{filename}")
def serve_user_avatar(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="头像不存在")
    path = avatar_upload_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="头像不存在")
    return FileResponse(path, media_type=avatar_media_type(filename))


@app.post("/api/user/avatar")
def upload_user_avatar(
    payload: AvatarUploadRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    content_type = payload.content_type.lower().split(";")[0].strip()
    suffix = AVATAR_ALLOWED_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=422, detail="头像仅支持 JPG、PNG 或 WebP 图片")
    raw_data = payload.data_base64
    if "," in raw_data and raw_data.split(",", 1)[0].lower().startswith("data:"):
        raw_data = raw_data.split(",", 1)[1]
    try:
        content = base64.b64decode(raw_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="头像图片解析失败，请重新上传") from exc
    if not content:
        raise HTTPException(status_code=422, detail="头像图片为空")
    if len(content) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=422, detail="头像图片建议控制在 2MB 以内")

    upload_dir = avatar_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"user_{current_user.id}_{uuid4().hex[:12]}{suffix}"
    path = upload_dir / filename
    path.write_bytes(content)
    current_user.avatar_url = f"/api/user/avatar/files/{filename}"
    db.commit()
    db.refresh(current_user)
    return {"avatar_url": current_user.avatar_url, "user": user_to_dict(current_user)}


@app.post("/api/user/upgrade")
def upgrade_user_to_pro(
    payload: UpgradeUserRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    if current_user.username not in {"normal@example", "pro@example"}:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "UPGRADE_CONTACT_REQUIRED",
                "message": "如需升级专业版，请联系客服 18960333566。",
                "data": {},
            },
        )
    old_plan = current_user.plan_type
    if current_user.plan_type != "pro":
        current_user.plan_type = "pro"
        current_user.pro_expire_at = current_user.pro_expire_at
        db.add(
            UpgradeLog(
                user_id=current_user.id,
                from_plan=old_plan,
                to_plan="pro",
                reason=payload.reason or "local_development",
            )
        )
        db.commit()
        db.refresh(current_user)
    return {"success": True, "new_version": current_user.plan_type, "user": user_to_dict(current_user)}


@app.get("/api/simulations")
def list_simulations(
    db: DbSession,
    current_user: CurrentUser,
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    project_status: str | None = Query(default=None, alias="status"),
) -> dict[str, Any]:
    filters = [SimulationProject.user_id == current_user.id]
    if project_status:
        status_value = project_status.strip()
        if status_value == "running":
            filters.append(SimulationProject.status.in_(ACTIVE_PROJECT_STATUSES))
        else:
            filters.append(SimulationProject.status == status_value)
    if page is not None or page_size is not None:
        current_page = page or 1
        current_page_size = page_size or limit or 20
        current_offset = (current_page - 1) * current_page_size
        current_limit = current_page_size
    else:
        current_limit = limit or 20
        current_offset = offset or 0
        current_page_size = current_limit
        current_page = current_offset // max(current_limit, 1) + 1
    total = db.scalar(select(func.count()).select_from(SimulationProject).where(*filters)) or 0
    stmt = (
        select(SimulationProject)
        .options(
            defer(SimulationProject.config_snapshot),
            defer(SimulationProject.market_config),
            defer(SimulationProject.product_definition),
            defer(SimulationProject.result_data),
        )
        .where(*filters)
        .order_by(
            sql_case((SimulationProject.project_name.like("【代表案例】%"), 0), else_=1),
            SimulationProject.updated_at.desc(),
            SimulationProject.id.desc(),
        )
        .offset(current_offset)
        .limit(current_limit)
    )
    return {
        "total": int(total),
        "limit": current_limit,
        "offset": current_offset,
        "page": current_page,
        "page_size": current_page_size,
        "items": [project_to_dict(row, include_configs=False) for row in db.scalars(stmt)],
    }


@app.get("/api/simulations/summary")
def simulations_summary(db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    """Return per-status project counts for the dashboard summary cards."""
    base_filter = [SimulationProject.user_id == current_user.id]
    draft = db.scalar(
        select(func.count()).select_from(SimulationProject).where(
            SimulationProject.user_id == current_user.id,
            SimulationProject.status == "draft",
        )
    ) or 0
    running = db.scalar(
        select(func.count()).select_from(SimulationProject).where(
            SimulationProject.user_id == current_user.id,
            SimulationProject.status.in_(ACTIVE_PROJECT_STATUSES),
        )
    ) or 0
    completed = db.scalar(
        select(func.count()).select_from(SimulationProject).where(
            SimulationProject.user_id == current_user.id,
            SimulationProject.status == "completed",
        )
    ) or 0
    total = db.scalar(
        select(func.count()).select_from(SimulationProject).where(*base_filter)
    ) or 0
    return {"draft": int(draft), "running": int(running), "completed": int(completed), "total": int(total)}


@app.post("/api/simulations", status_code=status.HTTP_201_CREATED)
def create_simulation(
    payload: CreateSimulationRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = SimulationProject(
        user_id=current_user.id,
        project_name=payload.project_name.strip(),
        status="draft",
        plan_type_used=current_user.plan_type,
        product_definition={},
        market_config={},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_to_dict(project)


@app.get("/api/simulations/{project_id}")
def get_simulation(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    return project_to_dict(get_owned_project(db, current_user, project_id))


@app.post("/api/simulations/{project_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_simulation(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    source = get_owned_project(db, current_user, project_id)
    cloned = SimulationProject(
        user_id=current_user.id,
        project_name=f"{source.project_name}（补录副本）"[:160],
        status="draft",
        plan_type_used=current_user.plan_type or source.plan_type_used or "basic",
        product_definition=dict(source.product_definition or {}),
        market_config=dict(source.market_config or {}),
        draft_version=1,
        quota_charged=False,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return project_to_dict(cloned)


@app.delete("/api/simulations/{project_id}")
def delete_simulation(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    if project.status == "running" or (project.status == "submitted" and project.task_id):
        raise HTTPException(status_code=409, detail="排队或运行中的项目请先取消任务")
    task_id = project.task_id
    client = get_redis_client()
    if task_id:
        remove_task_from_queues(client, task_id)
        client.delete(progress_key(task_id))
        client.delete(cancel_key(task_id))
        client.delete(f"simulation:heartbeat:{task_id}")
    client.delete(project_progress_key(project.id))
    client.delete(project_lock_key(project.id))
    for model in (CustomCompetitorBackfillJob, ExportTask, ShareToken, QuotaLog, DistillCheckLog, RagTraceLog, SimulationTaskLog):
        db.execute(delete(model).where(model.project_id == project.id))
    db.execute(delete(SimulationProject).where(SimulationProject.id == project.id))
    db.commit()
    return {"success": True, "project_id": project_id}


@app.get("/api/simulations/{project_id}/draft")
def get_simulation_draft(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    return project_to_dict(get_owned_project(db, current_user, project_id))


@app.put("/api/simulations/{project_id}/draft")
@app.patch("/api/simulations/{project_id}/draft")
def update_simulation_draft(
    project_id: int,
    payload: UpdateSimulationDraftRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    if project.status not in {"draft", "submitted", "failed"}:
        raise HTTPException(status_code=409, detail="当前状态不能编辑草稿")
    ensure_draft_version(project, payload.draft_version)
    if payload.project_name is not None:
        project.project_name = payload.project_name.strip()
    if payload.product_definition is not None:
        project.product_definition = payload.product_definition
    if payload.market_config is not None:
        project.market_config = payload.market_config
    project.status = "draft"
    project.draft_version += 1
    db.commit()
    db.refresh(project)
    return project_to_dict(project)


@app.put("/api/simulations/{project_id}/step1")
def save_step1(
    project_id: int,
    payload: Step1Request,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    ensure_draft_version(project, payload.draft_version)
    validate_step1_product_definition(payload.product_definition)
    if (project.plan_type_used or "basic") == "basic" and enabled_param_count(payload.product_definition) > 3:
        raise HTTPException(
            status_code=403,
            detail={"code": "BASIC_PARAM_LIMIT", "message": "普通版最多启用 3 个产品参数", "data": {}},
        )
    project.product_definition = payload.product_definition
    project.status = "draft"
    project.draft_version += 1
    db.commit()
    db.refresh(project)
    return project_to_dict(project)


@app.put("/api/simulations/{project_id}/step2")
def save_step2(
    project_id: int,
    payload: Step2Request,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    ensure_draft_version(project, payload.draft_version)
    if (project.plan_type_used or "basic") == "basic" and competitor_count(payload.market_config) > 1:
        raise HTTPException(
            status_code=403,
            detail={"code": "BASIC_COMPETITOR_LIMIT", "message": "普通版最多选择 1 个竞品", "data": {}},
        )
    project.market_config = validate_market_crowds(payload.market_config, project.plan_type_used or "basic")
    project.status = "draft"
    project.draft_version += 1
    db.commit()
    db.refresh(project)
    return project_to_dict(project)


@app.post("/api/simulations/{project_id}/submit")
def submit_simulation(
    project_id: int,
    payload: SubmitSimulationRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    product_definition = payload.product_definition or project.product_definition or {}
    market_config = payload.market_config or project.market_config or {}
    if not product_definition:
        raise HTTPException(status_code=422, detail="缺少产品定义")
    if not market_config:
        raise HTTPException(status_code=422, detail="缺少市场配置")
    validate_step1_product_definition(product_definition)
    product_definition, market_config = validate_version_limits(project, product_definition, market_config)

    snapshot, snapshot_hash = make_config_snapshot(project, current_user, product_definition, market_config)
    project.product_definition = product_definition
    project.market_config = market_config
    project.config_snapshot = snapshot
    project.snapshot_hash = snapshot_hash
    project.status = "submitted"
    project.plan_type_used = project.plan_type_used or current_user.plan_type
    project.simulation_version = snapshot["simulation_version"]
    project.error_code = None
    project.error_reason = None
    project.submitted_at = utc_now_naive()
    db.commit()
    db.refresh(project)
    return project_to_dict(project, include_snapshot=True)


@app.post("/api/simulations/{project_id}/run")
def run_simulation(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    if project.status not in {"submitted", "failed"}:
        raise HTTPException(status_code=409, detail="请先提交配置后再运行")
    if not project.config_snapshot or not project.snapshot_hash:
        raise HTTPException(status_code=422, detail="缺少提交快照")

    client = get_redis_client()
    lock_key = project_lock_key(project.id)
    task_id = f"sim_{uuid4().hex}"
    lock_set = client.set(lock_key, task_id, nx=True, ex=settings.task_timeout_seconds)
    if not lock_set:
        raise HTTPException(
            status_code=409,
            detail={"code": "TASK_ALREADY_RUNNING", "message": "该项目已有运行中的任务", "data": {}},
        )

    queue_name = queue_name_for_plan(project.plan_type_used)
    plan_type = project.plan_type_used or current_user.plan_type or "basic"
    target_duration_seconds = target_report_duration_seconds(task_id, plan_type)
    task_payload = {
        "task_id": task_id,
        "project_id": project.id,
        "user_id": current_user.id,
        "snapshot_hash": project.snapshot_hash,
        "queue": queue_name,
        "plan_type": plan_type,
        "target_duration_seconds": target_duration_seconds,
        "created_at": utc_now_iso(),
    }
    progress = {
        "task_id": task_id,
        "project_id": project.id,
        "status": "queued",
        "percent": 0,
        "stage": "queued",
        "message": "任务已提交，系统会按顺序自动开始",
        "plan_type": plan_type,
        "target_duration_seconds": target_duration_seconds,
        "remaining_seconds": target_duration_seconds,
        "estimated_start_at": utc_now_iso(),
        "estimated_completed_at": format_utc_iso(utc_now_naive() + timedelta(seconds=target_duration_seconds)),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    try:
        charge_quota_if_needed(db, current_user, project, task_id)
        project.task_id = task_id
        project.status = "submitted"
        project.started_at = None
        project.completed_at = None
        project.error_code = None
        project.error_reason = None
        db.commit()
        client.rpush(queue_name, json.dumps(task_payload, ensure_ascii=False))
        redis_json_set(progress_key(task_id), progress, ex=settings.redis_progress_expire_seconds)
        redis_json_set(project_progress_key(project.id), progress, ex=settings.redis_progress_expire_seconds)
        try:
            enqueue_project_backfill(db, project)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("自定义竞品低优先级复用任务入队失败，主仿真任务继续运行", extra={"project_id": project.id})
    except Exception:
        db.rollback()
        client.delete(lock_key)
        raise
    db.refresh(project)
    return {"task": build_progress_payload(project, progress), "project": project_to_dict(project)}


@app.get("/api/simulations/{project_id}/progress")
def get_simulation_progress(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    promote_report_waiting_if_ready(db, project)
    progress = redis_json_get(progress_key(project.task_id)) if project.task_id else None
    if progress is None:
        progress = redis_json_get(project_progress_key(project.id))
    return {"project": project_to_dict(project), "task": build_progress_payload(project, progress)}


@app.post("/api/simulations/{project_id}/cancel")
def cancel_simulation(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    if not project.task_id or project.status not in {"submitted", "running", REPORT_WAITING_STATUS}:
        raise HTTPException(status_code=409, detail="当前没有可取消的运行任务")

    client = get_redis_client()
    if project.status == REPORT_WAITING_STATUS:
        old_task_id = project.task_id
        client.delete(progress_key(old_task_id))
        client.delete(project_progress_key(project.id))
        client.delete(cancel_key(old_task_id))
        client.delete(f"simulation:heartbeat:{old_task_id}")
        client.delete(project_lock_key(project.id))
        rollback_quota_if_needed(db, project, old_task_id, "报告生成等待取消，回滚普通版次数")
        project.task_id = None
        project.status = "submitted"
        project.started_at = None
        project.completed_at = None
        project.result_data = None
        project.error_code = None
        project.error_reason = None
        db.commit()
        db.add(
            SimulationTaskLog(
                project_id=project.id,
                task_id=old_task_id,
                snapshot_id=project.snapshot_hash,
                stage="cancelled",
                log_level="warning",
                message="报告生成等待已取消，可重新运行",
                detail_json={},
            )
        )
        db.commit()
        db.refresh(project)
        return {
            "project": project_to_dict(project),
            "task": build_progress_payload(
                project,
                {
                    "task_id": None,
                    "project_id": project.id,
                    "status": "submitted",
                    "stage": "submitted",
                    "percent": 0,
                    "message": "报告生成等待已取消，可重新运行",
                    "updated_at": utc_now_iso(),
                },
            ),
        }

    progress = redis_json_get(progress_key(project.task_id)) or {}
    removed_from_queue = remove_task_from_queues(client, project.task_id)
    in_queue = bool(removed_from_queue) or str(progress.get("status") or "") in {"queued", "retrying"}
    if in_queue:
        old_task_id = project.task_id
        client.delete(progress_key(old_task_id))
        client.delete(project_progress_key(project.id))
        client.delete(cancel_key(old_task_id))
        client.delete(f"simulation:heartbeat:{old_task_id}")
        client.delete(project_lock_key(project.id))
        rollback_quota_if_needed(db, project, old_task_id, "排队任务取消，回滚普通版次数")
        project.task_id = None
        project.status = "submitted"
        project.started_at = None
        project.completed_at = None
        project.error_code = None
        project.error_reason = None
        db.commit()
        log = SimulationTaskLog(
            project_id=project.id,
            task_id=old_task_id,
            snapshot_id=project.snapshot_hash,
            stage="cancelled",
            log_level="warning",
            message="排队任务已取消，可重新运行",
            detail_json={"removed_from_queue": removed_from_queue},
        )
        db.add(log)
        db.commit()
        db.refresh(project)
        return {
            "project": project_to_dict(project),
            "task": build_progress_payload(
                project,
                {
                    "task_id": None,
                    "project_id": project.id,
                    "status": "submitted",
                    "stage": "submitted",
                    "percent": 0,
                    "message": "排队任务已取消，可重新运行",
                    "updated_at": utc_now_iso(),
                },
            ),
        }

    client.set(cancel_key(project.task_id), "1", ex=settings.task_timeout_seconds)
    progress.update(
        {
            "task_id": project.task_id,
            "project_id": project.id,
            "status": "cancel_requested",
            "stage": "cancel_requested",
            "message": "已请求取消，Worker 会在下一个检查点停止",
            "updated_at": utc_now_iso(),
        }
    )
    redis_json_set(progress_key(project.task_id), progress, ex=settings.redis_progress_expire_seconds)
    redis_json_set(project_progress_key(project.id), progress, ex=settings.redis_progress_expire_seconds)
    db.commit()
    db.refresh(project)
    return {"project": project_to_dict(project), "task": build_progress_payload(project, progress)}


@app.delete("/api/simulations/{project_id}/task")
def delete_simulation_task(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    return cancel_simulation(project_id, db, current_user)


@app.get("/api/simulations/{project_id}/logs")
def list_simulation_logs(
    project_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    rows = list(
        db.scalars(
            select(SimulationTaskLog)
            .where(SimulationTaskLog.project_id == project.id)
            .order_by(SimulationTaskLog.timestamp.desc(), SimulationTaskLog.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return {
        "project_id": project.id,
        "task_id": project.task_id,
        "total": len(rows),
        "items": [task_log_to_dict(item) for item in rows],
    }


@app.get("/api/simulations/{project_id}/report")
def get_report(project_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    promote_report_waiting_if_ready(db, project)
    if project.status == REPORT_WAITING_STATUS:
        remaining = report_wait_remaining_seconds(project.result_data or {})
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REPORT_NOT_READY",
                "message": "报告正在整理，请稍后刷新",
                "data": {
                    "remaining_seconds": remaining,
                    **report_wait_progress_extra(project.result_data or {}),
                },
            },
        )
    if project.status != "completed" or not project.result_data:
        raise HTTPException(status_code=404, detail="报告尚未生成")
    repair_project_report_data(db, project)
    report = with_project_report_fallbacks(sanitize_web_report(project.result_data, public=False), project)
    return {
        "project_id": project.id,
        "snapshot_hash": project.snapshot_hash,
        "status": project.status,
        "plan_type_used": project.plan_type_used,
        "report": report,
        "result_data": report,
    }


@app.post("/api/simulations/{project_id}/what-if")
def simulation_what_if(
    project_id: int,
    payload: WhatIfRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    if project.status != "completed" or not isinstance(project.result_data, dict):
        raise HTTPException(status_code=409, detail="项目完成后才能进行情景推演")
    report = project.result_data
    result: dict[str, Any] = {"project_id": project.id, "persisted": False}
    if payload.weights is not None:
        if set(payload.weights) != set(MAUT_WEIGHTS):
            raise HTTPException(status_code=422, detail="自定义权重必须完整包含五个决策维度")
        if any(not isinstance(value, (int, float)) or value < 0 for value in payload.weights.values()):
            raise HTTPException(status_code=422, detail="权重必须是非负数字")
        weights = normalize_weights(payload.weights)
        decisions = report.get("purchase_decisions") if isinstance(report.get("purchase_decisions"), list) else []
        scored = []
        for decision in decisions:
            if not isinstance(decision, dict) or not isinstance(decision.get("maut_scores"), dict):
                continue
            scored.append(
                (
                    weighted_purchase_intent(decision["maut_scores"], weights),
                    max(maut_safe_float(decision.get("sample_weight"), 1.0), 0.0),
                )
            )
        total_weight = sum(weight for _, weight in scored)
        if scored and total_weight:
            intent = sum(score * weight for score, weight in scored) / total_weight
        else:
            aggregation = report.get("aggregation") if isinstance(report.get("aggregation"), dict) else {}
            dimensions = aggregation.get("dimension_scores") if isinstance(aggregation.get("dimension_scores"), dict) else {}
            intent = sum(
                weights[key] * maut_safe_float((dimensions.get(key) or {}).get("avg_score"), 0.0)
                for key in weights
                if isinstance(dimensions.get(key), dict)
            )
        result["weight_scenario"] = {
            "template": "custom",
            "weights": weights,
            "purchase_intent": round(intent * 100, 1),
        }
    if payload.competitor_count is not None:
        chart = report.get("chart_data") if isinstance(report.get("chart_data"), dict) else {}
        scope = report.get("market_share_scope") if isinstance(report.get("market_share_scope"), dict) else chart.get("market_share_scope") or {}
        self_share = maut_safe_float(scope.get("simulation_environment_share"), 0.0)
        configured_count = max(1, int(maut_safe_float(scope.get("configured_competitor_count"), 1)))
        average_competitor_share = max(0.0, 100.0 - self_share) / configured_count
        denominator = self_share + average_competitor_share * payload.competitor_count
        result["market_share_scenario"] = {
            "competitor_count": payload.competitor_count,
            "share": round(self_share * 100 / denominator, 1) if denominator > 0 else 0.0,
            "relative_competitiveness_index": scope.get("relative_competitiveness_index"),
            "is_market_calibrated": False,
        }
    if payload.weights is None and payload.competitor_count is None:
        raise HTTPException(status_code=422, detail="至少提供自定义权重或竞品数量")
    return result


@app.post("/api/simulations/{project_id}/exports", status_code=status.HTTP_201_CREATED)
def create_export_task(
    project_id: int,
    payload: ExportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    promote_report_waiting_if_ready(db, project)
    if project.status != "completed":
        raise HTTPException(status_code=409, detail="项目完成后才能导出")
    if project.plan_type_used != "pro":
        raise HTTPException(
            status_code=403,
            detail={"code": "EXPORT_FORBIDDEN", "message": "普通版只能在线查看报告，专业版可导出", "data": {}},
        )
    repair_project_report_data(db, project)
    task = ExportTask(
        project_id=project.id,
        user_id=current_user.id,
        format=payload.format,
        status="queued" if payload.format == "pdf" else "processing",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    if payload.format == "pdf":
        export_payload = {
            "export_task_id": task.id,
            "project_id": project.id,
            "user_id": current_user.id,
            "format": payload.format,
            "created_at": utc_now_iso(),
        }
        client = get_redis_client()
        client.rpush(settings.redis_export_queue, json.dumps(export_payload, ensure_ascii=False))
        redis_json_set(
            export_progress_key(task.id),
            {
                "export_task_id": task.id,
                "project_id": project.id,
                "format": task.format,
                "status": task.status,
                "message": "PDF 已进入生成队列",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
            ex=settings.redis_progress_expire_seconds,
        )
        return {
            "export_task_id": task.id,
            "project_id": task.project_id,
            "format": task.format,
            "status": task.status,
            "download_url": task.download_url,
            "error_reason": task.error_reason,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        }
    try:
        write_export_file(task, project)
    except Exception as exc:
        task.status = "failed"
        task.error_reason = str(exc)
    db.commit()
    db.refresh(task)
    return {
        "export_task_id": task.id,
        "project_id": task.project_id,
        "format": task.format,
        "status": task.status,
        "download_url": task.download_url,
        "error_reason": task.error_reason,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@app.post("/api/simulations/{project_id}/export", status_code=status.HTTP_201_CREATED)
def create_export_task_alias(
    project_id: int,
    payload: ExportRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    return create_export_task(project_id, payload, db, current_user)


@app.get("/api/exports/{export_task_id}")
def get_export_task(export_task_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    task = get_owned_export_task(db, current_user, export_task_id)
    progress = redis_json_get(export_progress_key(task.id)) or {}
    return {
        "export_task_id": task.id,
        "project_id": task.project_id,
        "format": task.format,
        "status": progress.get("status") or task.status,
        "download_url": progress.get("download_url") or task.download_url,
        "error_reason": task.error_reason or progress.get("error_reason"),
        "message": progress.get("message"),
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@app.get("/api/exports/{export_task_id}/download")
def download_export_task(export_task_id: int, db: DbSession, current_user: CurrentUser) -> FileResponse:
    task = get_owned_export_task(db, current_user, export_task_id)
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="导出文件尚未完成")
    path = export_file_path(task)
    if not path.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")
    media_type_map = {
        "json": "application/json",
        "markdown": "text/markdown; charset=utf-8",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(task.format, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/api/exports/render/{token}")
def get_pdf_render_payload(token: str, db: DbSession) -> dict[str, Any]:
    payload = decode_pdf_render_token(token)
    project = db.get(SimulationProject, int(payload["project_id"]))
    if project is not None:
        promote_report_waiting_if_ready(db, project)
    if project is None or project.status != "completed" or not project.result_data:
        raise HTTPException(status_code=404, detail="PDF 渲染报告不存在")
    repair_project_report_data(db, project)
    return build_report_payload(project, public=True, compact=True)


@app.post("/api/simulations/{project_id}/share-tokens", status_code=status.HTTP_201_CREATED)
def create_project_share_token(
    project_id: int,
    payload: ShareTokenRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    project = get_owned_project(db, current_user, project_id)
    promote_report_waiting_if_ready(db, project)
    if project.status != "completed" or not project.result_data:
        raise HTTPException(status_code=409, detail="报告生成后才能分享")
    if project.plan_type_used != "pro":
        raise HTTPException(
            status_code=403,
            detail={"code": "SHARE_FORBIDDEN", "message": "普通版只能在线查看报告，专业版可分享", "data": {}},
        )
    repair_project_report_data(db, project)
    token = create_share_token()
    expires_at = utc_now_naive() + timedelta(hours=payload.expires_in_hours)
    item = ShareToken(
        token_hash=hash_share_token(token),
        project_id=project.id,
        created_by=current_user.id,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    api_base_url = settings.public_base_url.rstrip("/")
    frontend_base_url = settings.frontend_base_url.rstrip("/")
    api_share_url = f"{api_base_url}/api/share/{token}"
    frontend_share_url = f"{frontend_base_url}/share/{token}"
    return {
        "id": item.id,
        "project_id": item.project_id,
        "token": token,
        "share_url": frontend_share_url,
        "frontend_share_url": frontend_share_url,
        "api_share_url": api_share_url,
        "expires_at": item.expires_at,
        "is_active": item.is_active,
    }


@app.post("/api/simulations/{project_id}/share", status_code=status.HTTP_201_CREATED)
def create_project_share_token_alias(
    project_id: int,
    payload: ShareTokenRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    return create_project_share_token(project_id, payload, db, current_user)


@app.delete("/api/share-tokens/{share_token_id}")
def disable_share_token(share_token_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    item = db.scalar(
        select(ShareToken)
        .join(SimulationProject, SimulationProject.id == ShareToken.project_id)
        .where(
            ShareToken.id == share_token_id,
            SimulationProject.user_id == current_user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="分享链接不存在")
    item.is_active = False
    db.commit()
    return {"id": item.id, "is_active": item.is_active}


@app.post("/api/share/{token}/revoke")
def revoke_share_token_by_token(token: str, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    item = db.scalar(
        select(ShareToken)
        .join(SimulationProject, SimulationProject.id == ShareToken.project_id)
        .where(
            ShareToken.token_hash == hash_share_token(token),
            SimulationProject.user_id == current_user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="分享链接不存在")
    item.is_active = False
    db.commit()
    return {"id": item.id, "is_active": item.is_active}


@app.get("/api/share/{token}")
def get_public_shared_report(token: str, db: DbSession) -> dict[str, Any]:
    item = db.scalar(select(ShareToken).where(ShareToken.token_hash == hash_share_token(token)))
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="分享链接不存在或已关闭")
    if item.expires_at and item.expires_at < utc_now_naive():
        raise HTTPException(status_code=404, detail="分享链接已过期")
    project = db.get(SimulationProject, item.project_id)
    if project is not None:
        promote_report_waiting_if_ready(db, project)
    if project is None or project.status != "completed" or not project.result_data:
        raise HTTPException(status_code=404, detail="分享报告不存在")
    repair_project_report_data(db, project)
    payload = build_report_payload(project, public=True, compact=True)
    payload.update(
        {
            "expires_at": item.expires_at,
        }
    )
    return payload


@app.get("/api/feature-flags")
def list_feature_flags(db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    stmt = select(SystemFeatureFlag).order_by(SystemFeatureFlag.flag_name)
    items = [
        {
            "flag_name": row.flag_name,
            "is_enabled": row.is_enabled,
            "config_json": row.config_json or {},
            "description": row.description,
        }
        for row in db.scalars(stmt)
    ]
    return {"total": len(items), "items": items}
