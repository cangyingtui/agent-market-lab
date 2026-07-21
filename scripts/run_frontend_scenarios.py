from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.crowd_profile import normalize_crowd_profile  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.export_service import export_file_path  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DistillCheckLog, ExportTask, RagTraceLog, ShareToken, SimulationProject, SimulationTaskLog, User  # noqa: E402
from app.redis_client import get_redis_client, redis_json_get, redis_json_set  # noqa: E402
from app.task_keys import progress_key, project_lock_key, project_progress_key  # noqa: E402
from app.time_utils import utc_now_iso, utc_now_naive  # noqa: E402
from engine import worker  # noqa: E402
from engine.chart_data import build_chart_data  # noqa: E402


SCENARIOS = [
    {
        "name": "前端流程-高端智能手机",
        "product_definition": {
            "product_name": "高端智能手机",
            "brand": "智测样机",
            "category": "消费电子",
            "subcategory": "智能手机",
            "price_cny": 4999,
            "specifications": {"电池": "5000mAh", "屏幕": "OLED 120Hz", "防水": "IP68"},
        },
        "market_config": {
            "target_crowd": "高端用户",
            "strategy": "差异化定价",
            "scene": "线上首发",
            "crowd_profile": {
                "age_range": "28-45",
                "city_tier": "一线/新一线",
                "income_level": "高收入",
                "life_stage": "高端商务与科技尝鲜",
                "price_sensitivity": "low",
                "feature_priorities": ["续航", "屏幕", "防水"],
                "channel_preferences": ["品牌旗舰店", "内容种草", "科技媒体"],
                "purchase_motivations": ["体验升级", "效率提升", "品牌信任"],
                "risk_concerns": ["售后体验", "价格波动", "真实口碑"],
                "custom_description": "愿意为可靠体验和高端服务支付溢价，重视发布期口碑。",
            },
            "competitors": [],
        },
    },
    {
        "name": "前端流程-电动牙刷",
        "product_definition": {
            "product_name": "电动牙刷",
            "brand": "智测样机",
            "category": "家用电器",
            "subcategory": "电动牙刷",
            "price_cny": 399,
            "specifications": {"续航": "30天", "防水": "IPX7", "模式": "清洁/美白/敏感"},
        },
        "market_config": {
            "target_crowd": "注重口腔护理的年轻用户",
            "strategy": "功能差异化",
            "scene": "电商促销",
            "crowd_profile": {
                "age_range": "22-35",
                "city_tier": "一线/二线",
                "income_level": "中等收入",
                "life_stage": "年轻白领/租房独居",
                "price_sensitivity": "medium",
                "feature_priorities": ["续航", "防水", "清洁模式"],
                "channel_preferences": ["综合电商", "短视频平台", "内容种草"],
                "purchase_motivations": ["改善口腔护理", "颜值升级", "促销囤货"],
                "risk_concerns": ["刷头耗材成本", "噪音", "清洁效果真实性"],
                "custom_description": "愿意尝试功能升级，但会比较促销价和耗材成本。",
            },
            "competitors": [],
        },
    },
]


MULTI_SCHEME_SCENARIO = {
    "name": "前端流程-多方案手机",
    "product_definition": {
        "mode": "multi_scheme",
        "active_scheme_id": "scheme_base",
        "schemes": [
            {
                "scheme_id": "scheme_base",
                "scheme_name": "基础款",
                "product_name": "多方案智能手机基础款",
                "brand": "智测样机",
                "category": "消费电子",
                "subcategory": "智能手机",
                "price_cny": 3999,
                "specifications": {"电池": "4800mAh", "屏幕": "OLED 90Hz", "防水": "IP67"},
            },
            {
                "scheme_id": "scheme_pro",
                "scheme_name": "高端款",
                "product_name": "多方案智能手机高端款",
                "brand": "智测样机",
                "category": "消费电子",
                "subcategory": "智能手机",
                "price_cny": 5999,
                "specifications": {"电池": "5500mAh", "屏幕": "OLED 120Hz", "防水": "IP68", "影像": "潜望长焦"},
            },
        ],
    },
    "market_config": {
        "target_crowd": "高端商务与科技尝鲜用户",
        "strategy": "多价位方案对比",
        "scene": "线上首发",
        "crowd_profile": {
            "age_range": "28-45",
            "city_tier": "一线/新一线",
            "income_level": "高收入",
            "life_stage": "高端商务与科技尝鲜",
            "price_sensitivity": "low",
            "feature_priorities": ["续航", "屏幕", "影像"],
            "channel_preferences": ["品牌旗舰店", "科技媒体"],
            "purchase_motivations": ["体验升级", "效率提升"],
            "risk_concerns": ["售后体验", "价格波动"],
        },
        "competitors": [],
    },
}


PRIVATE_KEYS = {
    "access_token",
    "authorization",
    "api_key",
    "secret",
    "password",
    "prompt",
    "prompt_trace",
    "formal_test_log_path",
    "token_hash",
    "raw",
    "queries",
}

PUBLIC_FORBIDDEN_MARKERS = (
    "prompt_trace",
    "formal_test_log_path",
    "token_hash",
    "task_id",
    "snapshot_hash",
    "snapshot_id",
    "share_token_id",
    '"raw"',
    "api_key",
    "authorization",
    "password",
    "email",
    "user_id",
    "debug",
)


def compact(value: Any, max_chars: int = 5000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "chars": len(text), "preview": text[:max_chars]}


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in PRIVATE_KEYS or "api_key" in key_text or "secret" in key_text:
                continue
            if key_text == "token":
                continue
            sanitized[str(key)] = sanitize(item)
        return compact(sanitized)
    if isinstance(value, list):
        return compact([sanitize(item) for item in value])
    return value


def unwrap(body: Any) -> Any:
    if isinstance(body, dict) and "data" in body and "code" in body:
        return body["data"]
    return body


def response_json(response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw_text": response.text[:1000]}


def record_call(records: list[dict[str, Any]], label: str, method: str, path: str, response, started_at: float) -> Any:
    body = response_json(response)
    data = unwrap(body)
    records.append(
        {
            "label": label,
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "ok": 200 <= response.status_code < 400,
            "response_summary": sanitize(data),
        }
    )
    response.raise_for_status()
    return data


def api_call(
    client: TestClient,
    records: list[dict[str, Any]],
    label: str,
    method: str,
    path: str,
    record_path: str | None = None,
    **kwargs: Any,
) -> Any:
    started_at = time.perf_counter()
    response = client.request(method, path, **kwargs)
    return record_call(records, label, method, record_path or path, response, started_at)


def external_api_call(
    records: list[dict[str, Any]],
    label: str,
    method: str,
    path: str,
    record_path: str | None = None,
    **kwargs: Any,
) -> Any:
    started_at = time.perf_counter()
    url = f"{settings.public_base_url.rstrip('/')}{path}"
    with httpx.Client(timeout=90, trust_env=False) as http_client:
        response = http_client.request(method, url, **kwargs)
    return record_call(records, label, method, record_path or path, response, started_at)


def promote_to_pro(user_id: int) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise RuntimeError(f"用户不存在：{user_id}")
        user.plan_type = "pro"
        user.basic_quota_remaining = max(user.basic_quota_remaining, 2)
        db.commit()


def remove_task_from_queues(task_id: str, project_id: int) -> None:
    client = get_redis_client()
    for queue_name in (settings.redis_basic_queue, settings.redis_pro_queue, settings.redis_task_queue):
        for raw_item in client.lrange(queue_name, 0, -1):
            text = raw_item.decode("utf-8", errors="ignore") if isinstance(raw_item, bytes) else str(raw_item)
            if task_id in text:
                client.lrem(queue_name, 0, raw_item)
    client.delete(project_lock_key(project_id))


def active_product_definition(product_definition: dict[str, Any]) -> dict[str, Any]:
    if product_definition.get("mode") != "multi_scheme":
        return product_definition
    schemes = product_definition.get("schemes")
    if not isinstance(schemes, list) or not schemes:
        return product_definition
    active_id = product_definition.get("active_scheme_id")
    for item in schemes:
        if isinstance(item, dict) and item.get("scheme_id") == active_id:
            return {**item, "mode": "single_scheme", "source_mode": "multi_scheme"}
    first = schemes[0] if isinstance(schemes[0], dict) else {}
    return {**first, "mode": "single_scheme", "source_mode": "multi_scheme"}


def sample_report(scenario: dict[str, Any]) -> dict[str, Any]:
    product = active_product_definition(scenario["product_definition"])
    market = scenario["market_config"]
    aggregation = {"purchase_intent_avg": 0.68, "risk_points": ["需要真实证据验证"]}
    crowd_profile = normalize_crowd_profile(market)
    agent_samples = [{"agent_id": "sample_agent_001", "segment": market["target_crowd"], "budget": product["price_cny"]}]
    purchase_decisions = [{"agent_id": "sample_agent_001", "purchase_intent_score": 0.68, "decision": "consider"}]
    evidence = {
        "product_query": [],
        "competitor_query": [],
        "market_query": [{"source": "frontend_sample", "snippet": "用于验证前端接口和日志文件结构。"}],
    }
    chart_data = build_chart_data(
        {"product_definition": product, "market_config": market},
        evidence,
        agent_samples,
        purchase_decisions,
        aggregation,
        plan_type="pro",
    )
    return {
        "executive_summary": f"{product['product_name']} 的样例报告已生成，用于前端流程返回日志验证。",
        "target_segments": [{"name": market["target_crowd"], "insight": "关注功能可信度、价格解释和竞品差异。"}],
        "crowd_profile": crowd_profile,
        "competitor_insights": [{"source": "sample", "insight": "竞品证据待真实 Worker 补齐。"}],
        "pricing_analysis": {"summary": "样例价格分析；真实报告请关闭 --sample-report 运行。", "reference_price": product["price_cny"]},
        "strategy_recommendations": ["突出核心规格", "解释价格合理性", "保留竞品对比证据"],
        "risk_warnings": ["这是样例报告，不代表真实 LLM 判断。"],
        "evidence_used": [{"source": "frontend_sample", "snippet": "用于验证前端接口和日志文件结构。"}],
        "rag_summary": {
            "product_query": {"count": 0, "sources": []},
            "competitor_query": {"count": 0, "sources": []},
            "market_query": {"count": 1, "sources": ["frontend_sample"]},
        },
        "evidence_sources": [{"query_type": "market_query", "source": "frontend_sample", "snippet": "用于验证前端接口和日志文件结构。"}],
        "insight_evidence_map": {
            "executive_summary": ["market_query"],
            "strategy_recommendations": ["market_query"],
        },
        "model_validation": {
            "enabled": False,
            "status": "disabled",
            "validation_batch_id": None,
            "checked_samples": 0,
            "consistent_count": 0,
            "inconsistent_count": 0,
            "consistency_score": None,
            "threshold": 0.8,
            "warning_level": "info",
            "samples": [],
        },
        "agent_samples": agent_samples,
        "purchase_decisions": purchase_decisions,
        "aggregation": aggregation,
        "chart_data": chart_data,
        "quality_warnings": ["sample_report=true"],
        "is_fallback": True,
        "fallback_reason": "前端流程日志脚本使用样例报告快速验证导出和分享。",
    }


def complete_with_sample_report(project_id: int, task_id: str, scenario: dict[str, Any]) -> None:
    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        if project is None:
            raise RuntimeError(f"项目不存在：{project_id}")
        project.status = "completed"
        project.result_data = sample_report(scenario)
        project.completed_at = utc_now_naive()
        db.add(
            SimulationTaskLog(
                project_id=project.id,
                task_id=task_id,
                snapshot_id=project.snapshot_hash,
                stage="completed",
                log_level="info",
                message="前端流程日志脚本写入样例报告",
                detail_json={"sample_report": True},
            )
        )
        db.commit()
    redis_json_set(
        progress_key(task_id),
        progress_payload := {
            "task_id": task_id,
            "project_id": project_id,
            "status": "completed",
            "percent": 100,
            "stage": "completed",
            "message": "样例报告已写入",
            "updated_at": utc_now_iso(),
        },
        ex=settings.redis_progress_expire_seconds,
    )
    redis_json_set(project_progress_key(project_id), progress_payload, ex=settings.redis_progress_expire_seconds)
    remove_task_from_queues(task_id, project_id)


def public_security_summary(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    markers = [marker for marker in PUBLIC_FORBIDDEN_MARKERS if marker.lower() in text]
    return {"ok": not markers, "forbidden_markers": markers}


def v24_contract_summary(project_id: int, task_id: str, public_payload: dict[str, Any]) -> dict[str, Any]:
    task_progress = redis_json_get(progress_key(task_id))
    project_progress = redis_json_get(project_progress_key(project_id))
    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        if project is None:
            raise RuntimeError(f"项目不存在：{project_id}")
        snapshot = project.config_snapshot or {}
        result_data = project.result_data or {}
        rag_logs = list(db.scalars(select(RagTraceLog).where(RagTraceLog.project_id == project_id, RagTraceLog.task_id == task_id)))
        distill_count = len(list(db.scalars(select(DistillCheckLog).where(DistillCheckLog.project_id == project_id, DistillCheckLog.task_id == task_id))))
        task_log_count = len(list(db.scalars(select(SimulationTaskLog).where(SimulationTaskLog.project_id == project_id, SimulationTaskLog.task_id == task_id))))
        share_count = len(list(db.scalars(select(ShareToken).where(ShareToken.project_id == project_id))))
    rag_queries = snapshot.get("rag_search_queries") or snapshot.get("rag_queries") or {}
    snapshot_required = {"snapshot_id", "user_id", "submitted_at", "simulation_params", "rag_search_queries"}
    result_required = {"rag_summary", "evidence_sources", "insight_evidence_map", "model_validation"}
    product_definition = snapshot.get("product_definition") if isinstance(snapshot.get("product_definition"), dict) else {}
    multi_scheme = product_definition.get("mode") == "multi_scheme"
    scheme_results = result_data.get("scheme_results")
    comparison_summary = result_data.get("comparison_summary")
    return {
        "project_status": project.status,
        "multi_scheme": multi_scheme,
        "scheme_comparison_ok": (not multi_scheme)
        or (isinstance(scheme_results, list) and len(scheme_results) >= 2 and isinstance(comparison_summary, dict)),
        "snapshot_required_ok": snapshot_required.issubset(snapshot.keys()),
        "snapshot_missing": sorted(snapshot_required - set(snapshot.keys())),
        "rag_query_keys": sorted(rag_queries.keys()) if isinstance(rag_queries, dict) else [],
        "rag_query_keys_ok": set(rag_queries.keys()) == {"product_query", "competitor_query", "market_query"} if isinstance(rag_queries, dict) else False,
        "result_required_ok": result_required.issubset(result_data.keys()),
        "result_missing": sorted(result_required - set(result_data.keys())),
        "rag_trace_count": len(rag_logs),
        "rag_trace_query_types": sorted({item.query_type for item in rag_logs}),
        "distill_log_count": distill_count,
        "task_log_count": task_log_count,
        "share_token_count": share_count,
        "task_progress_cached": bool(task_progress),
        "project_progress_cached": bool(project_progress),
        "public_security": public_security_summary(public_payload),
    }


def acceptance_summary(progress: dict[str, Any], report: dict[str, Any], exports: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    required_export_status = {
        item["format"]: item["status"]
        for item in exports
        if item.get("format") in {"json", "markdown", "excel"}
    }
    checks = {
        "completed": progress.get("status") == "completed",
        "report_present": bool(report),
        "required_exports_completed": required_export_status == {"json": "completed", "markdown": "completed", "excel": "completed"},
        "public_report_sanitized": bool(contract.get("public_security", {}).get("ok")),
        "snapshot_contract_ok": bool(contract.get("snapshot_required_ok") and contract.get("rag_query_keys_ok")),
        "result_contract_ok": bool(contract.get("result_required_ok")),
        "progress_cache_ok": bool(contract.get("task_progress_cached") and contract.get("project_progress_cached")),
        "scheme_comparison_ok": bool(contract.get("scheme_comparison_ok")),
    }
    checks["critical_ok"] = all(checks.values())
    return checks


def chart_data_summary(report: dict[str, Any]) -> dict[str, Any]:
    chart_data = report.get("chart_data") if isinstance(report.get("chart_data"), dict) else {}
    market_share = chart_data.get("market_share") if isinstance(chart_data.get("market_share"), list) else []
    price_sensitivity = chart_data.get("price_sensitivity") if isinstance(chart_data.get("price_sensitivity"), list) else []
    overview = chart_data.get("overview_metrics") if isinstance(chart_data.get("overview_metrics"), dict) else {}
    return sanitize(
        {
            "prompt_version": chart_data.get("prompt_version"),
            "plan_type": chart_data.get("plan_type"),
            "overview_metrics": overview,
            "market_share": market_share,
            "market_share_total": round(sum(float(item.get("share") or item.get("value") or 0) for item in market_share if isinstance(item, dict)), 2),
            "price_sensitivity": price_sensitivity,
            "param_importance_count": len(chart_data.get("param_importance") or []) if isinstance(chart_data.get("param_importance"), list) else 0,
            "has_competitor_radar": isinstance(chart_data.get("competitor_radar"), dict),
            "has_sensitivity_waterfall": isinstance(chart_data.get("sensitivity_waterfall"), list),
        }
    )


def export_local_path(export_task_id: int) -> str:
    with SessionLocal() as db:
        task = db.get(ExportTask, export_task_id)
        if task is None:
            return ""
        path = export_file_path(task)
        return str(path) if path.exists() else str(path)


def public_report_text(payload: dict[str, Any], report: dict[str, Any]) -> str:
    chart = chart_data_summary(report)
    overview = chart.get("overview_metrics") if isinstance(chart.get("overview_metrics"), dict) else {}
    lines = [
        f"项目：{payload.get('project_name') or ''}",
        f"状态：{payload.get('status') or ''}",
        f"执行摘要：{report.get('executive_summary') or ''}",
        f"购买意愿指数：{overview.get('purchase_intent_index', '-')}",
        f"预估市场份额：{overview.get('estimated_market_share', '-')}",
        f"市场份额合计：{chart.get('market_share_total', '-')}",
        f"价格敏感曲线：{json.dumps(chart.get('price_sensitivity') or [], ensure_ascii=False, default=str)}",
        f"质量提示：{json.dumps(report.get('quality_warnings') or [], ensure_ascii=False, default=str)}",
    ]
    return "\n".join(lines)


def run_one_scenario(client: TestClient, scenario: dict[str, Any], run_worker: bool, sample_mode: bool) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    started_at = time.perf_counter()
    username = f"frontend_{uuid4().hex[:10]}"
    password = "12345678"

    register_data = api_call(
        client,
        records,
        "注册",
        "POST",
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    login_data = api_call(
        client,
        records,
        "登录",
        "POST",
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    token = str(login_data.get("access_token") or register_data.get("access_token"))
    headers = {"Authorization": f"Bearer {token}"}
    me_data = api_call(client, records, "读取当前用户", "GET", "/api/auth/me", headers=headers)
    promote_to_pro(int(me_data["id"]))
    api_call(client, records, "读取专业版用户信息", "GET", "/api/auth/me", headers=headers)

    project = api_call(
        client,
        records,
        "创建项目",
        "POST",
        "/api/simulations",
        headers=headers,
        json={"project_name": scenario["name"]},
    )
    project_id = int(project["id"])
    api_call(
        client,
        records,
        "保存 Step1 产品定义",
        "PUT",
        f"/api/simulations/{project_id}/step1",
        headers=headers,
        json={"product_definition": scenario["product_definition"]},
    )
    api_call(
        client,
        records,
        "保存 Step2 市场配置",
        "PUT",
        f"/api/simulations/{project_id}/step2",
        headers=headers,
        json={"market_config": scenario["market_config"]},
    )
    api_call(client, records, "提交配置", "POST", f"/api/simulations/{project_id}/submit", headers=headers, json={})
    if sample_mode:
        task_id = f"sample_{uuid4().hex}"
        records.append(
            {
                "label": "样例模式跳过 Redis 入队",
                "method": "LOCAL",
                "path": f"/api/simulations/{project_id}/run",
                "status_code": 200,
                "elapsed_ms": 0,
                "ok": True,
                "response_summary": {"task_id": task_id, "reason": "sample_report=true，不触发常驻 Worker"},
            }
        )
        complete_with_sample_report(project_id, task_id, scenario)
    else:
        run_data = api_call(client, records, "启动仿真", "POST", f"/api/simulations/{project_id}/run", headers=headers)
        task_id = str(run_data["task"]["task_id"])
        if run_worker:
            worker.run_loop(once=True, timeout=3)

    progress = api_call(client, records, "读取进度", "GET", f"/api/simulations/{project_id}/progress", headers=headers)
    logs_data = api_call(client, records, "读取运行日志", "GET", f"/api/simulations/{project_id}/logs", headers=headers)

    report_data: dict[str, Any] = {}
    public_payload: dict[str, Any] = {}
    export_items: list[dict[str, Any]] = []
    share_url = ""
    frontend_share_url = ""
    api_share_url = ""
    if progress.get("project", {}).get("status") == "completed":
        report_data = api_call(client, records, "读取报告", "GET", f"/api/simulations/{project_id}/report", headers=headers)
        for fmt in ("json", "markdown", "excel", "pdf"):
            try:
                call = external_api_call if fmt == "pdf" else api_call
                if fmt == "pdf":
                    export_data = call(
                        records,
                        f"创建 {fmt} 导出（真实 API）",
                        "POST",
                        f"/api/simulations/{project_id}/exports",
                        headers=headers,
                        json={"format": fmt},
                    )
                    export_status = call(
                        records,
                        f"读取 {fmt} 导出状态（真实 API）",
                        "GET",
                        f"/api/exports/{export_data['export_task_id']}",
                        headers=headers,
                    )
                else:
                    export_path = f"/api/simulations/{project_id}/export" if fmt == "json" else f"/api/simulations/{project_id}/exports"
                    export_data = call(
                        client,
                        records,
                        f"创建 {fmt} 导出",
                        "POST",
                        export_path,
                        headers=headers,
                        json={"format": fmt},
                    )
                    export_status = call(
                        client,
                        records,
                        f"读取 {fmt} 导出状态",
                        "GET",
                        f"/api/exports/{export_data['export_task_id']}",
                        headers=headers,
                    )
            except Exception as exc:
                export_items.append(
                    {
                        "format": fmt,
                        "export_task_id": None,
                        "status": "failed",
                        "download_url": None,
                        "error_reason": str(exc),
                        "local_file_path": "",
                    }
                )
                continue
            export_items.append(
                {
                    "format": fmt,
                    "export_task_id": export_status["export_task_id"],
                    "status": export_status["status"],
                    "download_url": export_status["download_url"],
                    "error_reason": export_status.get("error_reason"),
                    "local_file_path": export_local_path(int(export_status["export_task_id"])),
                }
            )
        share_data = api_call(
            client,
            records,
            "创建分享链接",
            "POST",
            f"/api/simulations/{project_id}/share",
            headers=headers,
            json={"expires_in_hours": 72},
        )
        share_url = str(share_data.get("share_url") or "")
        frontend_share_url = str(share_data.get("frontend_share_url") or share_url)
        api_share_url = str(share_data.get("api_share_url") or f"{settings.public_base_url.rstrip('/')}/api/share/{share_data['token']}")
        public_payload = api_call(
            client,
            records,
            "读取公开分享报告",
            "GET",
            f"/api/share/{share_data['token']}",
            record_path="/api/share/<token>",
        )
        alias_share_data = api_call(
            client,
            records,
            "创建待撤销分享链接",
            "POST",
            f"/api/simulations/{project_id}/share",
            headers=headers,
            json={"expires_in_hours": 72},
        )
        api_call(
            client,
            records,
            "按 token 撤销分享",
            "POST",
            f"/api/share/{alias_share_data['token']}/revoke",
            headers=headers,
            record_path="/api/share/<token>/revoke",
        )
        revoked_check = client.get(f"/api/share/{alias_share_data['token']}")
        records.append(
            {
                "label": "确认撤销后不可访问",
                "method": "GET",
                "path": "/api/share/<token>",
                "status_code": revoked_check.status_code,
                "elapsed_ms": 0,
                "ok": revoked_check.status_code == 404,
                "response_summary": sanitize(response_json(revoked_check)),
            }
        )

    report = report_data.get("report") or {}
    public_report = public_payload.get("report") if isinstance(public_payload.get("report"), dict) else report
    contract = v24_contract_summary(project_id, task_id, public_payload)
    acceptance = acceptance_summary(progress.get("task") or {}, report, export_items, contract)
    return {
        "scenario": scenario["name"],
        "project_id": project_id,
        "task_id": task_id,
        "sample_mode": sample_mode,
        "run_worker": run_worker,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "responses": records,
        "progress": sanitize(progress.get("task") or {}),
        "logs": sanitize(logs_data),
        "v24_contract": sanitize(contract),
        "acceptance": acceptance,
        "report_summary": sanitize(
            {
                "executive_summary": report.get("executive_summary"),
                "crowd_profile": report.get("crowd_profile"),
                "aggregation": report.get("aggregation"),
                "quality_warnings": report.get("quality_warnings"),
                "is_fallback": report.get("is_fallback"),
                "fallback_reason": report.get("fallback_reason"),
            }
        ),
        "chart_data_summary": chart_data_summary(report),
        "public_report_text": public_report_text(public_payload, public_report),
        "exports": export_items,
        "share_url": share_url,
        "frontend_share_url": frontend_share_url,
        "api_share_url": api_share_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行前端主流程对应的 API 场景，并保存返回日志")
    parser.add_argument("--limit", type=int, default=1, help="最多运行多少个内置场景")
    parser.add_argument("--run-dir", default="", help="指定日志目录，默认 logs/frontend_runs/YYYYMMDD_HHMMSS")
    parser.add_argument("--run-worker", action="store_true", help="真实消费 Redis 任务，生成真实 Worker 报告")
    parser.add_argument("--multi-scheme", action="store_true", help="追加一个 v2.4 专业版多方案场景")
    parser.add_argument(
        "--sample-report",
        action="store_true",
        help="快速写入样例 completed 报告，用于验证前端导出/分享/日志结构，不调用 LLM",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else PROJECT_ROOT / "logs" / "frontend_runs" / utc_now_naive().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.run_worker:
        os.environ["FORMAL_RUN_DIR"] = str(run_dir / "formal_worker_logs")

    client = TestClient(app)
    results: list[dict[str, Any]] = []
    summary_path = run_dir / "summary.jsonl"
    scenarios = list(SCENARIOS[: args.limit])
    if args.multi_scheme:
        scenarios.append(MULTI_SCHEME_SCENARIO)
    for index, scenario in enumerate(scenarios, 1):
        result = run_one_scenario(
            client,
            scenario,
            run_worker=args.run_worker,
            sample_mode=args.sample_report or not args.run_worker,
        )
        file_path = run_dir / f"scenario_{index:02d}_{result['project_id']}.json"
        file_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary = {
            "scenario": result["scenario"],
            "project_id": result["project_id"],
            "task_id": result["task_id"],
            "sample_mode": result["sample_mode"],
            "duration_ms": result["duration_ms"],
            "status": result["progress"].get("status"),
            "acceptance": result["acceptance"],
            "v24_contract": result["v24_contract"],
            "is_fallback": result["report_summary"].get("is_fallback"),
            "quality_warnings": result["report_summary"].get("quality_warnings", []),
            "chart_data_summary": result["chart_data_summary"],
            "exports": result["exports"],
            "share_url": result["share_url"],
            "frontend_share_url": result["frontend_share_url"],
            "api_share_url": result["api_share_url"],
            "log_path": str(file_path),
        }
        with summary_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
        results.append(summary)

    print(json.dumps({"run_dir": str(run_dir), "summary_path": str(summary_path), "items": results}, ensure_ascii=False, indent=2))
    return 0 if all(item["acceptance"].get("critical_ok") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
