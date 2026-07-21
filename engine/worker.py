from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import select
from sqlalchemy.orm.exc import ObjectDeletedError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.crowd_profile import canonicalize_market_crowds, crowd_profile_text, normalize_crowd_profile, normalize_crowd_segments  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import DistillCheckLog, QuotaLog, RagTraceLog, SimulationProject, SimulationTaskLog, User  # noqa: E402
from app.redis_client import get_redis_client, redis_json_get, redis_json_set  # noqa: E402
from app.runtime_status import (  # noqa: E402
    REPORT_WAITING_STAGE,
    REPORT_WAITING_STATUS,
    attach_report_wait_runtime,
    report_wait_progress_extra,
    report_wait_progress_percent,
    target_report_duration_seconds as runtime_target_report_duration_seconds,
)
from app.task_keys import cancel_key, heavy_resource_lock_key, progress_key, project_lock_key, project_progress_key  # noqa: E402
from app.time_utils import utc_now_iso, utc_now_naive  # noqa: E402
from engine.agent_generator import generate_agents  # noqa: E402
from engine.aggregation import aggregate_results  # noqa: E402
from engine.chart_data import build_chart_data  # noqa: E402
from engine.data_enrichment import candidate_to_evidence, run_data_enrichment  # noqa: E402
from engine.decision_model import generate_purchase_decisions  # noqa: E402
from engine.distill_client import run_distill_checks_if_enabled  # noqa: E402
from engine.evidence_utils import dedupe_and_rank, rag_contract_fields  # noqa: E402
from engine.fact_formatter import format_evidence_for_engine  # noqa: E402
from engine.formal_logger import compact, write_formal_task_log  # noqa: E402
from engine.maut_model import build_decision_model_summary, enrich_decisions_with_maut  # noqa: E402
from engine.report_generator import generate_simulation_report, split_evidence  # noqa: E402
from engine.social_simulation import run_social_simulation  # noqa: E402
from knowledge_model.product_evidence import search_product_evidence  # noqa: E402
from knowledge_model.rag_service import get_rag_service  # noqa: E402


class TaskCancelled(RuntimeError):
    pass


RETRYABLE_ERRORS = {
    "TimeoutError",
    "ConnectionError",
    "HTTPError",
    "RedisError",
    "OperationalError",
    "RuntimeError",
}


ERROR_CODE_MAP = {
    "TimeoutError": "TASK_TIMEOUT",
    "ConnectionError": "NETWORK_ERROR",
    "HTTPError": "NETWORK_ERROR",
    "RedisError": "REDIS_CONNECTION_ERROR",
    "OperationalError": "DB_CONNECTION_ERROR",
    "EmbeddingConfigError": "RAG_LOAD_ERROR",
    "FileNotFoundError": "RAG_INDEX_MISSING",
}


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
STAGE_WAIT_UPDATE_SECONDS = 30

ACTIVE_PROGRESS_STATUSES = {"queued", "submitted", "retrying", "running", REPORT_WAITING_STATUS}
TERMINAL_PROGRESS_STATUSES = {"completed", "failed", "cancelled"}
PROGRESS_TIME_KEYS = {
    "created_at",
    "estimated_start_at",
    "estimated_completed_at",
    "remaining_seconds",
    "queue_eta_seconds",
    "target_duration_seconds",
    "report_ready_at",
    "report_wait_started_at",
    "report_wait_target_seconds",
    "plan_type",
}


def normalize_error_code(exc: Exception) -> str:
    if isinstance(exc, TaskCancelled):
        return "TASK_CANCELLED"
    class_name = exc.__class__.__name__
    text = str(exc)
    if class_name in ERROR_CODE_MAP:
        return ERROR_CODE_MAP[class_name]
    if "timed out" in text.lower() or "timeout" in text.lower():
        return "LLM_API_TIMEOUT" if "llm" in text.lower() or "model" in text.lower() else "TASK_TIMEOUT"
    if "faiss" in text.lower() and ("missing" in text.lower() or "not found" in text.lower()):
        return "RAG_INDEX_MISSING"
    if "faiss" in text.lower() or "embedding" in text.lower():
        return "RAG_LOAD_ERROR"
    return "UNKNOWN_WORKER_ERROR" if class_name == "RuntimeError" else class_name


def worker_heartbeat(status: str, extra: dict[str, Any] | None = None) -> None:
    payload = {
        "worker_id": WORKER_ID,
        "status": status,
        "updated_at": utc_now_iso(),
    }
    if extra:
        payload.update({key: value for key, value in extra.items() if value is not None})
    redis_json_set(
        f"simulation:worker:{WORKER_ID}:heartbeat",
        payload,
        ex=max(settings.redis_heartbeat_ttl_seconds * 4, 60),
    )


def refresh_task_heartbeat(task_id: str, project_id: int, stage: str | None = None) -> None:
    get_redis_client().set(
        f"simulation:heartbeat:{task_id}",
        utc_now_iso(),
        ex=settings.redis_heartbeat_ttl_seconds,
    )
    worker_heartbeat("processing", {"task_id": task_id, "project_id": project_id, "stage": stage})


def start_task_heartbeat_lease(task_id: str, project_id: int) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    refresh_task_heartbeat(task_id, project_id)
    interval = max(1, min(5, settings.redis_heartbeat_ttl_seconds // 3))

    def keep_alive() -> None:
        while not stop_event.wait(interval):
            try:
                refresh_task_heartbeat(task_id, project_id)
            except Exception:
                # The main task path remains responsible for surfacing Redis failures.
                continue

    thread = threading.Thread(target=keep_alive, name=f"task-heartbeat-{task_id}", daemon=True)
    thread.start()
    return stop_event, thread


def stop_task_heartbeat_lease(stop_event: threading.Event, thread: threading.Thread) -> None:
    stop_event.set()
    thread.join(timeout=1)


def heavy_lock_owner(task_id: str) -> str:
    return f"simulation:{task_id}"


def acquire_heavy_resource_lock(task_id: str, project_id: int) -> str:
    client = get_redis_client()
    owner = heavy_lock_owner(task_id)
    lock_key = heavy_resource_lock_key()
    while not client.set(lock_key, owner, nx=True, ex=settings.heavy_resource_lock_ttl_seconds):
        check_cancel(task_id)
        update_progress(
            task_id,
            project_id,
            "running",
            8,
            "start",
            "正在等待前序任务完成，系统会自动继续",
            {"resource_waiting": True},
        )
        time.sleep(5)
    return owner


def release_heavy_resource_lock(owner: str | None) -> None:
    if not owner:
        return
    client = get_redis_client()
    lock_key = heavy_resource_lock_key()
    if client.get(lock_key) == owner:
        client.delete(lock_key)


def log_task(
    db,
    project: SimulationProject | None,
    task_id: str,
    stage: str,
    message: str,
    level: str = "info",
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        SimulationTaskLog(
            project_id=project.id if project else None,
            task_id=task_id,
            snapshot_id=project.snapshot_hash if project else None,
            stage=stage,
            log_level=level,
            message=message,
            detail_json=detail or {},
        )
    )
    db.commit()


def reload_project(db, project_id: int) -> SimulationProject | None:
    db.expire_all()
    if db.scalar(select(SimulationProject.id).where(SimulationProject.id == project_id)) is None:
        return None
    return db.get(SimulationProject, project_id, populate_existing=True)


def mark_orphan_task(
    db,
    task_id: str,
    project_id: int,
    message: str = "项目已删除，已跳过孤儿队列任务",
) -> None:
    db.rollback()
    db.add(
        SimulationTaskLog(
            project_id=None,
            task_id=task_id,
            stage="orphan_task",
            log_level="warning",
            message=message,
            detail_json={"project_id": project_id},
        )
    )
    db.commit()
    update_progress(task_id, project_id, "failed", 100, "orphan_task", message)


def update_progress(
    task_id: str,
    project_id: int,
    status: str,
    percent: int,
    stage: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    previous: dict[str, Any] = {}
    try:
        previous = redis_json_get(progress_key(task_id)) or redis_json_get(project_progress_key(project_id)) or {}
    except Exception:
        previous = {}
    raw_percent = max(0, min(100, int(percent or 0)))
    display_percent = raw_percent
    previous_status = str(previous.get("status") or "")
    if status in ACTIVE_PROGRESS_STATUSES and previous_status not in TERMINAL_PROGRESS_STATUSES:
        try:
            previous_percent = int(previous.get("percent") or 0)
        except (TypeError, ValueError):
            previous_percent = 0
        if 0 <= previous_percent < 100:
            display_percent = max(previous_percent, raw_percent)
    payload = {
        "task_id": task_id,
        "project_id": project_id,
        "status": status,
        "percent": display_percent,
        "raw_percent": raw_percent,
        "stage_percent": raw_percent,
        "stage": stage,
        "message": message,
        "updated_at": utc_now_iso(),
    }
    for key in PROGRESS_TIME_KEYS:
        if key in previous and previous.get(key) not in (None, "") and payload.get(key) in (None, ""):
            payload[key] = previous[key]
    if extra:
        payload.update(extra)
    payload["stage_percent"] = raw_percent
    redis_json_set(progress_key(task_id), payload, ex=settings.redis_progress_expire_seconds)
    redis_json_set(project_progress_key(project_id), payload, ex=settings.redis_progress_expire_seconds)
    refresh_task_heartbeat(task_id, project_id, stage)


def check_cancel(task_id: str) -> None:
    if get_redis_client().exists(cancel_key(task_id)):
        raise TaskCancelled("任务已取消")


def report_duration_bounds(plan_type: str) -> tuple[int, int]:
    if plan_type == "pro":
        min_seconds = settings.pro_report_min_seconds
        max_seconds = settings.pro_report_max_seconds
    else:
        min_seconds = settings.basic_report_min_seconds
        max_seconds = settings.basic_report_max_seconds
    min_seconds = max(0, int(min_seconds))
    max_seconds = max(min_seconds, int(max_seconds))
    return min_seconds, max_seconds


def target_report_duration_seconds(task_id: str, plan_type: str) -> int:
    min_seconds, max_seconds = report_duration_bounds(plan_type)
    if max_seconds <= min_seconds:
        return min_seconds
    digest = hashlib.sha256(f"{task_id}:{plan_type}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    return min_seconds + seed % (max_seconds - min_seconds + 1)


def iso_after_seconds(seconds: int) -> str:
    return (utc_now_naive() + timedelta(seconds=max(0, seconds))).replace(microsecond=0).isoformat() + "Z"


def stage_wait_message(stage: str, remaining_seconds: int) -> str:
    messages = {
        "rag": "正在检索并整理市场证据",
        "agent_generation": "正在生成消费者画像与代表 Agent",
        "social_propagation": "正在模拟多轮社交传播",
        "aggregation": "正在聚合仿真指标",
        "assemble_report": "正在整理仿真报告",
    }
    prefix = messages.get(stage, "正在推进仿真任务")
    if remaining_seconds <= 0:
        return f"{prefix}，即将完成"
    minutes = max(1, (remaining_seconds + 59) // 60)
    return f"{prefix}，预计整体还需约 {minutes} 分钟"


def wait_until_stage_target(
    db,
    project: SimulationProject,
    task_id: str,
    started_monotonic: float,
    target_duration_seconds: int,
    target_ratio: float,
    stage: str,
    start_percent: int,
    end_percent: int,
) -> None:
    stage_target_seconds = round(target_duration_seconds * max(0.0, min(1.0, target_ratio)))
    elapsed_seconds = int(time.monotonic() - started_monotonic)
    stage_remaining_seconds = max(0, stage_target_seconds - elapsed_seconds)
    overall_remaining_seconds = max(0, target_duration_seconds - elapsed_seconds)
    if stage_remaining_seconds <= 0:
        update_progress(
            task_id,
            project.id,
            "running",
            end_percent,
            stage,
            stage_wait_message(stage, overall_remaining_seconds),
            {
                "elapsed_seconds": elapsed_seconds,
                "remaining_seconds": overall_remaining_seconds,
                "target_duration_seconds": target_duration_seconds,
                "estimated_completed_at": iso_after_seconds(overall_remaining_seconds),
                "simulation_waiting": False,
                "report_waiting": False,
            },
        )
        return

    log_task(
        db,
        project,
        task_id,
        stage,
        stage_wait_message(stage, overall_remaining_seconds),
        detail={
            "plan_type": project.plan_type_used or "basic",
            "elapsed_seconds": elapsed_seconds,
            "remaining_seconds": overall_remaining_seconds,
            "stage_target_seconds": stage_target_seconds,
            "target_duration_seconds": target_duration_seconds,
        },
    )

    while stage_remaining_seconds > 0:
        check_cancel(task_id)
        elapsed_seconds = int(time.monotonic() - started_monotonic)
        stage_remaining_seconds = max(0, stage_target_seconds - elapsed_seconds)
        overall_remaining_seconds = max(0, target_duration_seconds - elapsed_seconds)
        if stage_remaining_seconds <= 0:
            break
        progress_ratio = elapsed_seconds / max(1, stage_target_seconds)
        progress_percent = min(end_percent, max(start_percent, start_percent + int(progress_ratio * (end_percent - start_percent))))
        update_progress(
            task_id,
            project.id,
            "running",
            progress_percent,
            stage,
            stage_wait_message(stage, overall_remaining_seconds),
            {
                "elapsed_seconds": elapsed_seconds,
                "remaining_seconds": overall_remaining_seconds,
                "stage_target_seconds": stage_target_seconds,
                "target_duration_seconds": target_duration_seconds,
                "estimated_completed_at": iso_after_seconds(overall_remaining_seconds),
                "simulation_waiting": True,
                "report_waiting": stage == "assemble_report",
            },
        )
        project.last_heartbeat_at = utc_now_naive()
        db.commit()
        time.sleep(min(STAGE_WAIT_UPDATE_SECONDS, stage_remaining_seconds))

    elapsed_seconds = int(time.monotonic() - started_monotonic)
    overall_remaining_seconds = max(0, target_duration_seconds - elapsed_seconds)
    update_progress(
        task_id,
        project.id,
        "running",
        end_percent,
        stage,
        stage_wait_message(stage, overall_remaining_seconds),
        {
            "elapsed_seconds": elapsed_seconds,
            "remaining_seconds": overall_remaining_seconds,
            "target_duration_seconds": target_duration_seconds,
            "estimated_completed_at": iso_after_seconds(overall_remaining_seconds),
            "simulation_waiting": False,
            "report_waiting": False,
        },
    )


def rollback_quota_if_needed(db, project: SimulationProject, task_id: str, reason: str) -> None:
    if not project.quota_charged:
        return
    user = db.get(User, project.user_id)
    if user is None or project.plan_type_used == "pro":
        project.quota_charged = False
        return
    user.basic_quota_remaining += 1
    project.quota_charged = False
    db.add(
        QuotaLog(
            user_id=user.id,
            project_id=project.id,
            task_id=task_id,
            change_type="rollback",
            change_amount=1,
            reason=reason,
        )
    )


def should_retry(project: SimulationProject, exc: Exception) -> bool:
    if isinstance(exc, TaskCancelled):
        return False
    if project.retry_count >= project.max_retry:
        return False
    return exc.__class__.__name__ in RETRYABLE_ERRORS


def requeue_task(task: dict[str, Any], project: SimulationProject) -> None:
    queue_name = str(task.get("queue") or settings.redis_basic_queue)
    payload = {**task, "retry_count": project.retry_count, "requeued_at": utc_now_iso()}
    get_redis_client().rpush(queue_name, json.dumps(payload, ensure_ascii=False))


def active_product_definition(product_definition: dict[str, Any]) -> dict[str, Any]:
    if product_definition.get("mode") != "multi_scheme":
        return product_definition
    schemes = product_definition.get("schemes") if isinstance(product_definition.get("schemes"), list) else []
    active_scheme_id = product_definition.get("active_scheme_id")
    active = next(
        (
            item
            for item in schemes
            if isinstance(item, dict) and str(item.get("scheme_id")) == str(active_scheme_id)
        ),
        None,
    )
    if active is None:
        active = next((item for item in schemes if isinstance(item, dict)), None)
    if active is None:
        return product_definition
    return {**active, "mode": "single_scheme", "source_mode": "multi_scheme", "active_scheme_id": active.get("scheme_id")}


def runtime_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    product = snapshot.get("product_definition") if isinstance(snapshot.get("product_definition"), dict) else {}
    active = active_product_definition(product)
    if active is product:
        return snapshot
    return {
        **snapshot,
        "original_product_definition": product,
        "product_definition": active,
    }


def build_queries(snapshot: dict[str, Any]) -> dict[str, str]:
    structured = snapshot.get("rag_search_queries") or snapshot.get("rag_queries")
    if isinstance(structured, dict):
        queries = {
            key: str(structured.get(key) or "").strip()
            for key in ("product_query", "competitor_query", "market_query")
        }
        if all(queries.values()):
            return queries
    product = snapshot.get("product_definition") or {}
    market = canonicalize_market_crowds(snapshot.get("market_config") or {})
    rag_search_text = snapshot.get("rag_search_text") or ""
    product_name = product.get("product_name") or product.get("name") or "产品"
    category = product.get("subcategory") or product.get("category") or ""
    brand = product.get("brand") or ""
    target = market.get("target_crowd") or market.get("crowd") or ""
    strategy_items = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    strategy_names = []
    for item in strategy_items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("strategy") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            strategy_names.append(name)
    strategy = "；".join(dict.fromkeys(strategy_names)) or str(market.get("strategy") or "").strip()
    scene = market.get("scene") or ""
    profile_text = crowd_profile_text(market)

    return {
        "product_query": f"{rag_search_text} {brand} {product_name} 功能 参数 价格".strip(),
        "competitor_query": f"{rag_search_text} {category} {brand} {product_name} 竞品 对比 价格 规格".strip(),
        "market_query": f"{category} {product_name} {target} {profile_text} {strategy} {scene} 人群 场景 渠道 营销".strip(),
    }


def run_rag_queries(
    db,
    project: SimulationProject,
    task_id: str,
    queries: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    service = None
    service_error: Exception | None = None
    try:
        service = get_rag_service()
    except Exception as exc:
        service_error = exc
        log_task(
            db,
            project,
            task_id,
            "rag",
            "FAISS 服务暂不可用，使用结构化证据和降级证据继续仿真",
            "warning",
            {"error_class": exc.__class__.__name__, "error": str(exc)},
        )
    snapshot = project.config_snapshot or {}
    product_definition = snapshot.get("product_definition") or {}
    evidence: dict[str, list[dict[str, Any]]] = {}
    total = len(queries)

    def search_faiss(
        query_type: str,
        query_text: str,
        *,
        top_k: int,
        candidate_k: int,
    ) -> list[dict[str, Any]]:
        if service is None:
            exc = service_error or RuntimeError("FAISS 服务未初始化")
            return [
                {
                    "type": "rag_error",
                    "score": 0.0,
                    "source": "faiss_unavailable",
                    "source_type": "system_warning",
                    "rank": 0,
                    "matched_fields": ["rag_error"],
                    "snippet": f"FAISS ANN 检索暂不可用：{exc}",
                    "raw": {"query_type": query_type, "query": query_text, "error_class": exc.__class__.__name__, "error": str(exc)},
                }
            ]
        try:
            return service.search(
                query_text,
                top_k=top_k,
                source_include=["user_profile"],
                candidate_k=candidate_k,
            )
        except Exception as exc:
            log_task(
                db,
                project,
                task_id,
                f"rag:{query_type}",
                "FAISS ANN 检索失败，使用结构化证据和降级证据继续仿真",
                "warning",
                {"error_class": exc.__class__.__name__, "error": str(exc)},
            )
            return [
                {
                    "type": "rag_error",
                    "score": 0.0,
                    "source": "faiss_query_failed",
                    "source_type": "system_warning",
                    "rank": 0,
                    "matched_fields": ["rag_error"],
                    "snippet": f"FAISS ANN 检索失败：{exc}",
                    "raw": {"query_type": query_type, "query": query_text, "error_class": exc.__class__.__name__, "error": str(exc)},
                }
            ]

    for index, (query_type, query_text) in enumerate(queries.items(), 1):
        check_cancel(task_id)
        percent = 20 + int(index / max(1, total) * 50)
        update_progress(task_id, project.id, "running", percent, f"rag:{query_type}", "正在执行 RAG 检索")
        product_items: list[dict[str, Any]] = []
        faiss_items: list[dict[str, Any]] = []

        if query_type in {"product_query", "competitor_query"}:
            product_items = search_product_evidence(
                db,
                product_definition,
                query_text,
                top_k=settings.rag_top_k,
            )

        if query_type == "product_query":
            faiss_items = search_faiss(
                query_type,
                query_text,
                top_k=max(2, settings.rag_top_k // 2),
                candidate_k=settings.rag_top_k * 8,
            )
            items = [*product_items[:3], *faiss_items]
        elif query_type == "market_query":
            items = search_faiss(
                query_type,
                query_text,
                top_k=settings.rag_top_k,
                candidate_k=settings.rag_top_k * 10,
            )
        else:
            faiss_items = search_faiss(
                query_type,
                query_text,
                top_k=settings.rag_top_k,
                candidate_k=settings.rag_top_k * 8,
            )
            items = [*product_items, *faiss_items]

        final_items = dedupe_and_rank(items, limit=10)
        evidence[query_type] = final_items
        db.add(
            RagTraceLog(
                project_id=project.id,
                task_id=task_id,
                snapshot_id=project.snapshot_hash,
                query_type=query_type,
                query_text=query_text,
                top_k=settings.rag_top_k,
                retrieved_items=items,
                final_used_items=final_items,
            )
        )
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            log_task(
                db,
                None,
                task_id,
                "rag_trace",
                "RAG trace 写入失败，主流程继续；可能是测试清理或项目删除导致的孤儿任务",
                "warning",
                {"project_id": project.id, "error_class": exc.__class__.__name__, "error": str(exc)[:300]},
            )
    return evidence


def persist_distill_logs(
    db,
    project: SimulationProject,
    task_id: str,
    model_validation: dict[str, Any],
) -> None:
    samples = model_validation.get("samples") if isinstance(model_validation.get("samples"), list) else []
    validation_batch_id = model_validation.get("validation_batch_id")
    for index, sample in enumerate(samples, 1):
        if not isinstance(sample, dict):
            continue
        db.add(
            DistillCheckLog(
                project_id=project.id,
                task_id=task_id,
                snapshot_id=project.snapshot_hash,
                validation_batch_id=str(validation_batch_id or ""),
                sample_id=str(sample.get("sample_id") or sample.get("agent_id") or f"sample_{index:03d}"),
                input_text=sample.get("input_text") or sample.get("distill_input_text") or sample.get("text") or sample.get("reason"),
                agent_label=sample.get("agent_label") or sample.get("agent_decision") or sample.get("decision"),
                distill_label=sample.get("distill_label") or sample.get("predicted_label"),
                confidence=sample.get("confidence") if isinstance(sample.get("confidence"), (int, float)) else None,
                is_consistent=sample.get("is_consistent") if isinstance(sample.get("is_consistent"), bool) else None,
                judge_reason=sample.get("judge_reason") or sample.get("reason"),
            )
        )
    if samples:
        db.commit()


def build_scheme_comparison(
    original_snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    aggregation: dict[str, Any],
    plan_type: str,
) -> dict[str, Any] | None:
    product_definition = original_snapshot.get("product_definition")
    if not isinstance(product_definition, dict) or product_definition.get("mode") != "multi_scheme":
        return None
    schemes = [item for item in product_definition.get("schemes", []) if isinstance(item, dict)]
    if not schemes:
        return None
    scheme_results: list[dict[str, Any]] = []
    for index, scheme in enumerate(schemes, 1):
        scheme_snapshot = {**original_snapshot, "product_definition": scheme}
        scheme_chart_data = build_chart_data(
            scheme_snapshot,
            evidence,
            agents,
            decisions,
            aggregation,
            plan_type=plan_type,
        )
        overview = scheme_chart_data.get("overview_metrics") if isinstance(scheme_chart_data.get("overview_metrics"), dict) else {}
        scheme_results.append(
            {
                "scheme_id": scheme.get("scheme_id") or f"scheme_{index}",
                "scheme_name": scheme.get("scheme_name") or scheme.get("product_name") or f"方案{index}",
                "product_name": scheme.get("product_name") or scheme.get("name"),
                "purchase_intent": overview.get("purchase_intent_index"),
                "market_share": overview.get("estimated_market_share"),
                "target_match": overview.get("target_match"),
                "chart_data": scheme_chart_data,
            }
        )
    best = max(
        scheme_results,
        key=lambda item: (float(item.get("purchase_intent") or 0), float(item.get("market_share") or 0)),
    )
    first_intent = float(scheme_results[0].get("purchase_intent") or 0)
    best_intent = float(best.get("purchase_intent") or 0)
    return {
        "mode": "multi_scheme",
        "scheme_results": scheme_results,
        "comparison_summary": {
            "best_scheme_id": best.get("scheme_id"),
            "best_reason": f"{best.get('scheme_name')} 在当前共享市场配置下综合指标最高。",
            "intent_gap": round(best_intent - first_intent, 1),
        },
    }


def process_task(task: dict[str, Any]) -> None:
    task_started_monotonic = time.monotonic()
    task_id = str(task["task_id"])
    project_id = int(task["project_id"])
    client = get_redis_client()
    heavy_owner: str | None = None
    worker_heartbeat("processing", {"task_id": task_id, "project_id": project_id})

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        if project is None:
            log_task(db, None, task_id, "load_project", "项目不存在", "error", {"project_id": project_id})
            update_progress(task_id, project_id, "failed", 100, "orphan_task", "项目不存在，已跳过孤儿队列任务")
            client.delete(project_lock_key(project_id))
            client.delete(f"simulation:heartbeat:{task_id}")
            worker_heartbeat("idle")
            return

        heartbeat_stop, heartbeat_thread = start_task_heartbeat_lease(task_id, project_id)
        try:
            check_cancel(task_id)
            project.status = "running"
            project.started_at = utc_now_naive()
            project.last_heartbeat_at = utc_now_naive()
            project.error_code = None
            project.error_reason = None
            db.commit()

            heavy_owner = acquire_heavy_resource_lock(task_id, project.id)
            plan_type = project.plan_type_used or "basic"
            target_duration_seconds = runtime_target_report_duration_seconds(task_id, plan_type)
            log_task(db, project, task_id, "start", "Worker 已开始处理任务")
            update_progress(
                task_id,
                project.id,
                "running",
                10,
                "start",
                "系统已开始处理任务",
                {
                    "elapsed_seconds": 0,
                    "created_at": task.get("created_at") or utc_now_iso(),
                    "remaining_seconds": target_duration_seconds,
                    "target_duration_seconds": target_duration_seconds,
                    "estimated_completed_at": iso_after_seconds(target_duration_seconds),
                    "report_waiting": False,
                },
            )
            client.set(
                f"simulation:heartbeat:{task_id}",
                utc_now_iso(),
                ex=settings.redis_heartbeat_ttl_seconds,
            )

            original_snapshot = project.config_snapshot or {}
            snapshot = runtime_snapshot(original_snapshot)
            queries = build_queries(snapshot)
            log_task(db, project, task_id, "rag", "准备执行三类 RAG 查询", detail={"queries": queries})
            update_progress(task_id, project.id, "running", 18, "rag", "正在检索市场证据")
            evidence = run_rag_queries(db, project, task_id, queries)
            enrichment_result = run_data_enrichment(snapshot, evidence)
            enrichment_candidates = enrichment_result.get("candidates") if isinstance(enrichment_result.get("candidates"), list) else []
            auto_filled_prices = enrichment_result.get("auto_filled_prices") if isinstance(enrichment_result.get("auto_filled_prices"), list) else []
            if enrichment_candidates:
                auto_filled_ids = {
                    str(item.get("product_id"))
                    for item in auto_filled_prices
                    if isinstance(item, dict) and item.get("product_id") is not None
                }
                evidence.setdefault("competitor_query", []).extend(
                    candidate_to_evidence(candidate, index)
                    for index, candidate in enumerate(enrichment_candidates, 1)
                    if isinstance(candidate, dict) and str(candidate.get("product_id")) not in auto_filled_ids
                )
                log_task(
                    db,
                    project,
                    task_id,
                    "data_enrichment",
                    f"已生成 {len(enrichment_candidates)} 条网页补全，其中自动回填价格 {len(auto_filled_prices)} 条，未写入正式产品库",
                    detail={
                        "candidate_count": len(enrichment_candidates),
                        "auto_filled_price_count": len(auto_filled_prices),
                        "status": enrichment_result.get("status"),
                    },
                )
            elif enrichment_result.get("enabled"):
                log_task(
                    db,
                    project,
                    task_id,
                    "data_enrichment",
                    "数据补全未生成候选，主流程继续",
                    "warning",
                    {"status": enrichment_result.get("status"), "reason": enrichment_result.get("reason"), "errors": enrichment_result.get("errors")},
                )

            check_cancel(task_id)
            update_progress(task_id, project.id, "running", 30, "rag", "市场证据已整理完成")
            update_progress(task_id, project.id, "running", 32, "agent_generation", "正在生成消费者画像与代表 Agent")
            formatted_evidence = format_evidence_for_engine(evidence)
            agent_result = generate_agents(snapshot, evidence)
            agents = agent_result["agents"]

            check_cancel(task_id)
            update_progress(task_id, project.id, "running", 58, "agent_generation", "消费者样本已生成")
            update_progress(task_id, project.id, "running", 60, "purchase_decision", "正在模拟 Agent 购买决策")
            decision_result = generate_purchase_decisions(snapshot, evidence, agents)
            purchase_decisions = decision_result["decisions"]
            if not all(isinstance(item, dict) and isinstance(item.get("maut_scores"), dict) for item in purchase_decisions):
                purchase_decisions = enrich_decisions_with_maut(
                    snapshot,
                    evidence,
                    agents,
                    purchase_decisions,
                    override_score=False,
                )
            social_simulation = run_social_simulation(
                snapshot,
                evidence,
                agents,
                purchase_decisions,
                network_metadata=agent_result.get("social_network"),
                check_cancel=lambda: check_cancel(task_id),
                on_round=lambda round_number, total_rounds, summary: update_progress(
                    task_id,
                    project.id,
                    "running",
                    min(76, 62 + round_number * 4),
                    "social_propagation",
                    f"正在执行社交传播：第 {round_number}/{total_rounds} 轮",
                    {
                        "social_round": round_number,
                        "social_round_total": total_rounds,
                        "social_purchase_intent": summary.get("overall_purchase_intent"),
                        "social_max_score_change": summary.get("max_score_change"),
                    },
                ),
                validate_round=lambda decisions: run_distill_checks_if_enabled(snapshot, agents, decisions),
            )
            purchase_decisions = social_simulation.pop("final_decisions")
            model_validation = social_simulation.pop("final_validation")
            decision_model_summary = build_decision_model_summary(purchase_decisions)
            log_task(
                db,
                project,
                task_id,
                "social_propagation",
                f"社交传播已完成，共执行 {social_simulation.get('rounds_executed', 0)} 轮",
                detail={
                    "rounds_executed": social_simulation.get("rounds_executed"),
                    "converged": social_simulation.get("converged"),
                    "node_count": social_simulation.get("node_count"),
                    "edge_count": social_simulation.get("edge_count"),
                    "average_degree": social_simulation.get("average_degree"),
                },
            )
            update_progress(task_id, project.id, "running", 78, "social_propagation", "多轮社交传播已完成")

            update_progress(
                task_id,
                project.id,
                "running",
                80,
                "aux_validation",
                "辅助模型已完成逐轮一致性复核"
                if settings.enable_distill_check
                else "辅助模型复核：当前未启用外部小模型，已跳过实际调用",
            )
            distill_summary = model_validation
            persist_distill_logs(db, project, task_id, model_validation)
            log_task(
                db,
                project,
                task_id,
                "aux_validation",
                "辅助模型复核已完成；当前未启用外部小模型" if not distill_summary.get("enabled") else "辅助模型复核已返回结果",
                detail={
                    "enabled": model_validation.get("enabled", False),
                    "status": model_validation.get("status"),
                    "validation_batch_id": model_validation.get("validation_batch_id"),
                    "checked_samples": model_validation.get("checked_samples"),
                    "consistency_score": model_validation.get("consistency_score"),
                },
            )

            check_cancel(task_id)
            update_progress(task_id, project.id, "running", 82, "aggregation", "正在聚合仿真指标")
            aggregation = aggregate_results(agents, purchase_decisions, evidence, snapshot, social_simulation=social_simulation)
            chart_data = build_chart_data(
                snapshot,
                evidence,
                agents,
                purchase_decisions,
                aggregation,
                plan_type=project.plan_type_used or "basic",
            )
            update_progress(task_id, project.id, "running", 88, "aggregation", "仿真指标已汇总完成")

            check_cancel(task_id)
            update_progress(task_id, project.id, "running", 90, "assemble_report", "正在生成仿真报告")
            result_data = generate_simulation_report(snapshot, evidence)
            evidence_groups = split_evidence(evidence)
            rag_contract = rag_contract_fields(evidence)
            result_data["snapshot_hash"] = project.snapshot_hash
            result_data["snapshot_id"] = snapshot.get("snapshot_id")
            result_data["queries"] = queries
            result_data["rag_evidence"] = evidence
            result_data["final_rag_evidence"] = {
                key: dedupe_and_rank(items, limit=10)
                for key, items in evidence.items()
            }
            result_data.update(rag_contract)
            result_data["formatted_evidence"] = formatted_evidence
            result_data["data_enrichment"] = {key: value for key, value in enrichment_result.items() if key != "candidates"}
            result_data["data_enrichment_candidates"] = enrichment_candidates
            result_data["market_config"] = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
            result_data["crowd_profile"] = normalize_crowd_profile(snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {})
            result_data["crowd_segments"] = normalize_crowd_segments(snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {})
            result_data["agent_samples"] = agents
            result_data["purchase_decisions"] = purchase_decisions
            result_data["decision_model"] = decision_model_summary
            result_data["distill_summary"] = distill_summary
            result_data["model_validation"] = model_validation
            result_data["social_simulation"] = social_simulation
            result_data["aggregation"] = aggregation
            result_data["chart_data"] = chart_data
            result_data["plan_type_used"] = project.plan_type_used or "basic"
            result_data["data_quality"] = aggregation.get("evidence_quality", {})
            result_data["purchase_intent"] = chart_data["overview_metrics"]["purchase_intent_index"]
            result_data["market_share"] = chart_data["overview_metrics"]["estimated_market_share"]
            result_data["target_match"] = chart_data["overview_metrics"]["target_match"]
            result_data.update(evidence_groups)
            scheme_comparison = build_scheme_comparison(
                original_snapshot,
                evidence,
                agents,
                purchase_decisions,
                aggregation,
                plan_type=project.plan_type_used or "basic",
            )
            if scheme_comparison:
                result_data.update(scheme_comparison)
            prompt_trace = result_data.get("prompt_trace") if isinstance(result_data.get("prompt_trace"), dict) else {}
            prompt_trace["agent_generator"] = {
                "prompt_version": agent_result["prompt_version"],
                "is_fallback": False,
            }
            prompt_trace["decision_model"] = decision_result.get("prompt_trace", {})
            prompt_trace["distill_check"] = {
                "enabled": model_validation.get("enabled", False),
                "status": model_validation.get("status"),
                "validation_batch_id": model_validation.get("validation_batch_id"),
            }
            prompt_trace["social_simulation"] = {
                "prompt_version": social_simulation.get("prompt_version"),
                "rounds_executed": social_simulation.get("rounds_executed"),
                "converged": social_simulation.get("converged"),
                "network_implementation": social_simulation.get("implementation"),
            }
            prompt_trace["aggregation"] = {
                "prompt_version": aggregation["prompt_version"],
                "is_fallback": False,
            }
            prompt_trace["fact_formatter"] = {
                "prompt_version": formatted_evidence["prompt_version"],
                "is_fallback": False,
            }
            result_data["prompt_trace"] = prompt_trace
            result_data["metrics"] = {
                "evidence_groups": len(evidence),
                "evidence_items": sum(len(items) for items in evidence.values()),
                "structured_product_items": len(evidence_groups["structured_product_evidence"]),
                "user_profile_items": len(evidence_groups["user_profile_evidence"]),
                "market_strategy_items": len(evidence_groups["market_strategy_evidence"]),
                "agent_count": len(agents),
                "decision_count": len(purchase_decisions),
                "social_rounds_executed": social_simulation.get("rounds_executed"),
                "social_network_node_count": social_simulation.get("node_count"),
                "social_network_edge_count": social_simulation.get("edge_count"),
                "purchase_intent_avg": aggregation["purchase_intent_avg"],
                "estimated_market_share": chart_data["overview_metrics"]["estimated_market_share"],
                "product_price_coverage_pct": aggregation.get("evidence_quality", {}).get("price_coverage_pct", 0),
                "target_report_duration_seconds": target_duration_seconds,
            }
            actual_duration_seconds = int(time.monotonic() - task_started_monotonic)
            result_data["metrics"]["actual_report_duration_seconds"] = actual_duration_seconds
            formal_log_path = write_formal_task_log(
                scenario_name=str(snapshot.get("project_name") or project.project_name),
                task_id=task_id,
                payload={
                    "status": "completed",
                    "project_id": project.id,
                    "snapshot_hash": project.snapshot_hash,
                    "config_snapshot": compact(snapshot),
                    "rag_evidence_summary": compact(formatted_evidence),
                    "data_enrichment": compact(enrichment_result),
                    "agent_samples": compact(agents),
                    "purchase_decisions": compact(purchase_decisions),
                    "decision_model": compact(decision_model_summary),
                    "model_validation": compact(model_validation),
                    "social_simulation": compact(social_simulation),
                    "aggregation": compact(aggregation),
                    "chart_data": compact(chart_data),
                    "prompt_trace": compact(prompt_trace),
                    "metrics": result_data["metrics"],
                    "quality_warnings": result_data.get("quality_warnings", []),
                    "is_fallback": result_data.get("is_fallback"),
                    "report": compact(result_data),
                },
            )
            result_data["formal_test_log_path"] = formal_log_path
            generated_at = utc_now_naive()
            attach_report_wait_runtime(
                result_data,
                task_id,
                project.plan_type_used or "basic",
                project.started_at,
                generated_at,
            )
            wait_extra = report_wait_progress_extra(result_data, generated_at)
            wait_remaining_seconds = max(0, int(wait_extra.get("remaining_seconds") or 0))
            project.result_data = result_data
            project.last_heartbeat_at = generated_at
            if wait_remaining_seconds > 0:
                project.status = REPORT_WAITING_STATUS
                project.completed_at = None
            else:
                project.status = "completed"
                project.completed_at = generated_at
            db.commit()

            if wait_remaining_seconds > 0:
                log_task(
                    db,
                    project,
                    task_id,
                    REPORT_WAITING_STAGE,
                    "报告数据已生成，正在整理最终展示",
                    detail={
                        "plan_type": project.plan_type_used or "basic",
                        "elapsed_seconds": actual_duration_seconds,
                        "remaining_seconds": wait_remaining_seconds,
                        "target_duration_seconds": target_duration_seconds,
                    },
                )
                update_progress(
                    task_id,
                    project.id,
                    REPORT_WAITING_STATUS,
                    report_wait_progress_percent(result_data, generated_at),
                    REPORT_WAITING_STAGE,
                    "报告正在生成，请稍后",
                    {
                        **wait_extra,
                        "elapsed_seconds": actual_duration_seconds,
                        "created_at": task.get("created_at") or wait_extra.get("report_wait_started_at"),
                        "estimated_start_at": project.started_at.replace(microsecond=0).isoformat() + "Z" if project.started_at else wait_extra.get("report_wait_started_at"),
                        "target_duration_seconds": target_duration_seconds,
                        "report_waiting": True,
                    },
                )
            else:
                log_task(db, project, task_id, "completed", "任务处理完成")
                update_progress(
                    task_id,
                    project.id,
                    "completed",
                    100,
                    "completed",
                    "任务已完成",
                    {
                        "completed_at": utc_now_iso(),
                        "elapsed_seconds": actual_duration_seconds,
                        "remaining_seconds": 0,
                        "target_duration_seconds": target_duration_seconds,
                        "report_waiting": False,
                    },
                )
        except TaskCancelled:
            db.rollback()
            project = reload_project(db, project_id)
            if project is None:
                mark_orphan_task(db, task_id, project_id)
                return
            project.status = "failed"
            project.error_code = "TASK_CANCELLED"
            project.error_reason = "任务已取消"
            project.completed_at = utc_now_naive()
            rollback_quota_if_needed(db, project, task_id, "任务取消，回滚普通版次数")
            db.commit()
            log_task(db, project, task_id, "cancelled", "任务已取消", "warning")
            update_progress(task_id, project.id, "cancelled", 100, "cancelled", "任务已取消")
        except Exception as exc:
            db.rollback()
            project = reload_project(db, project_id)
            if project is None:
                mark_orphan_task(db, task_id, project_id)
                return
            error_code = normalize_error_code(exc)
            if should_retry(project, exc):
                project.retry_count += 1
                project.status = "submitted"
                project.error_code = error_code
                project.error_reason = f"第 {project.retry_count} 次重试排队：{exc}"
                db.commit()
                requeue_task(task, project)
                log_task(
                    db,
                    project,
                    task_id,
                    "retry",
                    project.error_reason,
                    "warning",
                    {"retry_count": project.retry_count, "max_retry": project.max_retry},
                )
                update_progress(
                    task_id,
                    project.id,
                    "retrying",
                    5,
                    "retry",
                    project.error_reason,
                    {"retry_count": project.retry_count, "max_retry": project.max_retry},
                )
            else:
                project.status = "failed"
                project.error_code = error_code
                project.error_reason = str(exc)
                project.completed_at = utc_now_naive()
                rollback_quota_if_needed(db, project, task_id, "任务失败，回滚普通版次数")
                db.commit()
                log_task(db, project, task_id, "failed", str(exc), "error")
                update_progress(task_id, project.id, "failed", 100, "failed", str(exc))
                if task.get("raise_on_failure"):
                    raise
        finally:
            stop_task_heartbeat_lease(heartbeat_stop, heartbeat_thread)
            release_heavy_resource_lock(heavy_owner)
            client.delete(project_lock_key(project_id))
            client.delete(f"simulation:heartbeat:{task_id}")
            worker_heartbeat("idle")


def pop_task(timeout: int) -> dict[str, Any] | None:
    client = get_redis_client()
    queues = [settings.redis_pro_queue, settings.redis_basic_queue, settings.redis_task_queue]
    worker_heartbeat("waiting", {"queues": queues})
    try:
        result = client.blpop(queues, timeout=timeout)
    except RedisTimeoutError:
        worker_heartbeat("idle", {"queues": queues})
        return None
    if result is None:
        worker_heartbeat("idle", {"queues": queues})
        return None
    _, raw = result
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Redis task payload must be a JSON object.")
    return data


def run_loop(once: bool, timeout: int) -> int:
    while True:
        task = pop_task(timeout=timeout)
        if task is None:
            if once:
                return 0
            continue
        try:
            process_task(task)
        except ObjectDeletedError:
            task_id = str(task.get("task_id") or "")
            project_id = int(task.get("project_id") or 0)
            with SessionLocal() as db:
                mark_orphan_task(db, task_id, project_id)
        if once:
            return 0
        time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser(description="产品市场仿真 Redis Worker")
    parser.add_argument("--once", action="store_true", help="只消费一个任务后退出")
    parser.add_argument("--timeout", type=int, default=5, help="等待队列任务的秒数")
    args = parser.parse_args()
    return run_loop(once=args.once, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
