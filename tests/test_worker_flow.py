from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import SimulationProject, SimulationTaskLog
from app.redis_client import get_redis_client, redis_json_get
from app.task_keys import cancel_key, progress_key, project_progress_key
from app.runtime_status import RUNTIME_META_KEY, format_utc_iso
from app.time_utils import utc_now_naive
from engine import monitor, worker


@pytest.fixture(autouse=True)
def skip_report_wait(monkeypatch) -> None:
    monkeypatch.setattr(worker, "wait_until_stage_target", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker.settings, "basic_report_min_seconds", 0)
    monkeypatch.setattr(worker.settings, "basic_report_max_seconds", 0)
    monkeypatch.setattr(worker.settings, "pro_report_min_seconds", 0)
    monkeypatch.setattr(worker.settings, "pro_report_max_seconds", 0)


class FakeRagService:
    def search(
        self,
        query: str,
        top_k: int | None = None,
        source_include: list[str] | None = None,
        candidate_k: int | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        return [
            {
                "type": "rag_fact",
                "score": 0.88,
                "source": "用户画像数据_pytest",
                "source_type": "user_profile",
                "rank": 1,
                "matched_fields": ["ann_vector", "keyword:性价比"],
                "snippet": "用户关注的关键词：性价比;防水;续航",
                "raw": {"query": query, "source_include": source_include, "candidate_k": candidate_k},
            }
        ]


def create_submitted_project(
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> int:
    created = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest Worker"})
    created.raise_for_status()
    project_id = created.json()["id"]
    client.put(
        f"/api/simulations/{project_id}/step1",
        headers=auth_headers,
        json={"product_definition": sample_product_definition},
    ).raise_for_status()
    client.put(
        f"/api/simulations/{project_id}/step2",
        headers=auth_headers,
        json={"market_config": sample_market_config},
    ).raise_for_status()
    client.post(f"/api/simulations/{project_id}/submit", headers=auth_headers, json={}).raise_for_status()
    return project_id


def run_project(client: TestClient, headers: dict[str, str], project_id: int) -> str:
    queued = client.post(f"/api/simulations/{project_id}/run", headers=headers)
    queued.raise_for_status()
    return queued.json()["task"]["task_id"]


@pytest.mark.no_db
def test_worker_idle_redis_timeout_is_treated_as_empty_queue(monkeypatch) -> None:
    class TimeoutRedis:
        def blpop(self, *_args, **_kwargs):
            raise worker.RedisTimeoutError("pytest idle timeout")

    heartbeat_states: list[str] = []
    monkeypatch.setattr(worker, "get_redis_client", lambda: TimeoutRedis())
    monkeypatch.setattr(worker, "worker_heartbeat", lambda state, *_args, **_kwargs: heartbeat_states.append(state))

    assert worker.pop_task(timeout=1) is None
    assert heartbeat_states == ["waiting", "idle"]


@pytest.mark.no_db
def test_task_heartbeat_lease_refreshes_until_stopped(monkeypatch) -> None:
    class RecordingRedis:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int | None]] = []

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            self.calls.append((key, value, ex))

    redis = RecordingRedis()
    monkeypatch.setattr(worker, "get_redis_client", lambda: redis)
    monkeypatch.setattr(worker, "worker_heartbeat", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker.settings, "redis_heartbeat_ttl_seconds", 3)

    stop_event, thread = worker.start_task_heartbeat_lease("pytest_task", 7)
    time.sleep(1.2)
    worker.stop_task_heartbeat_lease(stop_event, thread)

    assert len(redis.calls) >= 2
    assert all(key == "simulation:heartbeat:pytest_task" for key, _, _ in redis.calls)
    assert all(ex == 3 for _, _, ex in redis.calls)
    assert thread.is_alive() is False


def test_worker_success_generates_report(
    monkeypatch,
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    monkeypatch.setattr(worker, "get_rag_service", lambda: FakeRagService())
    monkeypatch.setattr(
        worker,
        "generate_purchase_decisions",
        lambda snapshot, evidence, agents: {
            "prompt_version": "decision_model_pytest",
            "decisions": [
                {
                    "agent_id": agent["agent_id"],
                    "purchase_intent_score": 0.72,
                    "decision": "buy",
                    "drivers": ["续航"],
                    "blockers": [],
                    "reason": "pytest",
                    "evidence_refs": [],
                }
                for agent in agents
            ],
            "is_fallback": True,
            "prompt_trace": {"prompt_version": "decision_model_pytest"},
        },
    )
    monkeypatch.setattr(worker, "write_formal_task_log", lambda **_: "logs/formal_runs/pytest/task.json")
    monkeypatch.setattr(
        worker,
        "generate_simulation_report",
        lambda snapshot, evidence: {
            "executive_summary": "pytest 报告摘要",
            "target_segments": [{"name": "高端用户", "insight": "关注续航"}],
            "competitor_insights": [{"source": "product:1", "insight": "竞品证据"}],
            "pricing_analysis": {"reference_price": 3999, "summary": "价格分析"},
            "strategy_recommendations": ["突出防水和续航"],
            "risk_warnings": ["价格数据需要复核"],
            "evidence_used": [{"source": "用户画像数据_pytest", "snippet": "用户证据"}],
            "is_fallback": False,
        },
    )
    project_id = create_submitted_project(client, auth_headers, sample_product_definition, sample_market_config)
    task_id = run_project(client, auth_headers, project_id)

    assert worker.run_loop(once=True, timeout=1) == 0

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        assert project.task_id == task_id
        assert project.status == "completed"
        assert project.result_data
        assert project.result_data["is_fallback"] is False or project.result_data["is_fallback"] is True
        assert "executive_summary" in project.result_data
        assert project.result_data["metrics"]["evidence_groups"] == 3
        assert set(project.result_data["queries"]) == {"product_query", "competitor_query", "market_query"}
        assert "rag_summary" in project.result_data
        assert "evidence_sources" in project.result_data
        assert "insight_evidence_map" in project.result_data
        assert "model_validation" in project.result_data
        assert project.result_data["agent_samples"]
        assert project.result_data["purchase_decisions"]
        assert "maut_scores" in project.result_data["purchase_decisions"][0]
        assert project.result_data["crowd_profile"]["city_tier"] == "一线/新一线"
        assert project.result_data["agent_samples"][0]["channel_preferences"] == ["品牌旗舰店", "内容种草"]
        assert "decision_model" in project.result_data
        assert 0 <= project.result_data["aggregation"]["purchase_intent_avg"] <= 1
        assert "dimension_scores" in project.result_data["aggregation"]
        assert "confidence" in project.result_data["aggregation"]
        assert project.result_data["social_simulation"]["rounds_executed"] >= 1
        assert project.result_data["social_simulation"]["node_count"] >= 60
        assert project.result_data["chart_data"]["social_evolution"]
        assert project.result_data["plan_type_used"] == "basic"
        assert "chart_data" in project.result_data
        assert round(sum(item["share"] for item in project.result_data["chart_data"]["market_share"]), 1) == 100.0
        assert project.result_data["chart_data"]["overview_metrics"]["purchase_intent_index"] == round(
            project.result_data["aggregation"]["purchase_intent_avg"] * 100,
            1,
        )
        assert project.result_data["formal_test_log_path"] == "logs/formal_runs/pytest/task.json"

    report = client.get(f"/api/simulations/{project_id}/report", headers=auth_headers)
    assert report.status_code == 200
    assert "executive_summary" in report.json()["report"]
    assert "chart_data" in report.json()["report"]


def test_worker_report_waiting_is_promoted_by_monitor(
    monkeypatch,
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    monkeypatch.setattr(worker.settings, "basic_report_min_seconds", 3600)
    monkeypatch.setattr(worker.settings, "basic_report_max_seconds", 3600)
    monkeypatch.setattr(worker, "get_rag_service", lambda: FakeRagService())
    monkeypatch.setattr(
        worker,
        "generate_purchase_decisions",
        lambda snapshot, evidence, agents: {
            "prompt_version": "decision_model_pytest",
            "decisions": [
                {
                    "agent_id": agent["agent_id"],
                    "purchase_intent_score": 0.72,
                    "decision": "buy",
                    "drivers": ["续航"],
                    "blockers": [],
                    "reason": "pytest",
                    "evidence_refs": [],
                }
                for agent in agents
            ],
            "prompt_trace": {"prompt_version": "decision_model_pytest"},
        },
    )
    monkeypatch.setattr(worker, "write_formal_task_log", lambda **_: "logs/formal_runs/pytest/task.json")
    monkeypatch.setattr(
        worker,
        "generate_simulation_report",
        lambda snapshot, evidence: {
            "executive_summary": "pytest 报告摘要",
            "target_segments": [{"name": "高端用户", "insight": "关注续航"}],
            "competitor_insights": [{"source": "product:1", "insight": "竞品证据"}],
            "pricing_analysis": {"reference_price": 3999, "summary": "价格分析"},
            "strategy_recommendations": ["突出防水和续航"],
            "risk_warnings": [],
            "evidence_used": [{"source": "用户画像数据_pytest", "snippet": "用户证据"}],
            "is_fallback": False,
        },
    )
    project_id = create_submitted_project(client, auth_headers, sample_product_definition, sample_market_config)
    task_id = run_project(client, auth_headers, project_id)

    assert worker.run_loop(once=True, timeout=1) == 0

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        assert project.status == "report_waiting"
        assert project.result_data
        runtime = project.result_data[RUNTIME_META_KEY]
        runtime["report_ready_at"] = format_utc_iso(utc_now_naive() - timedelta(seconds=1))
        project.result_data = {**project.result_data, RUNTIME_META_KEY: runtime}
        db.commit()

    result = monitor.scan_once(project_id=project_id)
    assert result["report_promoted"] == 1

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        assert project.status == "completed"

    progress = redis_json_get(progress_key(task_id))
    assert progress
    assert progress["status"] == "completed"
    assert progress["stage"] == "completed"


def test_worker_cancel_marks_project_cancelled(
    monkeypatch,
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    monkeypatch.setattr(worker, "get_rag_service", lambda: FakeRagService())
    project_id = create_submitted_project(client, auth_headers, sample_product_definition, sample_market_config)
    task_id = run_project(client, auth_headers, project_id)
    get_redis_client().set(cancel_key(task_id), "1")

    assert worker.run_loop(once=True, timeout=1) == 0

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        assert project.status == "failed"
        assert project.error_code == "TASK_CANCELLED"
        assert project.quota_charged is False


def test_worker_skips_project_deleted_after_task_is_popped(
    monkeypatch,
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = client.post("/api/simulations", headers=auth_headers, json={"project_name": "pytest 删除竞态"})
    created.raise_for_status()
    project_id = created.json()["id"]
    task_id = f"pytest_orphan_{project_id}"
    deleted = False

    def delete_project(_: str) -> None:
        nonlocal deleted
        if deleted:
            return
        deleted = True
        with SessionLocal() as other_db:
            other_db.execute(delete(SimulationProject).where(SimulationProject.id == project_id))
            other_db.commit()

    monkeypatch.setattr(worker, "check_cancel", delete_project)

    worker.process_task({"task_id": task_id, "project_id": project_id})

    progress = redis_json_get(progress_key(task_id))
    assert progress
    assert progress["status"] == "failed"
    assert progress["stage"] == "orphan_task"
    with SessionLocal() as db:
        log = db.scalar(select(SimulationTaskLog).where(SimulationTaskLog.task_id == task_id))
        assert log is not None
        assert log.project_id is None
        db.execute(delete(SimulationTaskLog).where(SimulationTaskLog.task_id == task_id))
        db.commit()
    redis = get_redis_client()
    redis.delete(progress_key(task_id))
    redis.delete(project_progress_key(project_id))


def test_worker_failure_writes_error(
    monkeypatch,
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    def raise_report(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("pytest worker failure")

    monkeypatch.setattr(worker, "get_rag_service", lambda: FakeRagService())
    monkeypatch.setattr(
        worker,
        "generate_purchase_decisions",
        lambda snapshot, evidence, agents: {
            "decisions": [
                {
                    "agent_id": agent["agent_id"],
                    "purchase_intent_score": 0.5,
                    "decision": "consider",
                    "drivers": [],
                    "blockers": [],
                    "reason": "pytest",
                    "evidence_refs": [],
                }
                for agent in agents
            ],
            "prompt_trace": {},
        },
    )
    monkeypatch.setattr(worker, "generate_simulation_report", raise_report)
    project_id = create_submitted_project(client, auth_headers, sample_product_definition, sample_market_config)
    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        project.max_retry = 0
        db.commit()
    run_project(client, auth_headers, project_id)

    assert worker.run_loop(once=True, timeout=1) == 0

    with SessionLocal() as db:
        project = db.scalar(select(SimulationProject).where(SimulationProject.id == project_id))
        assert project is not None
        assert project.status == "failed"
        assert project.error_code == "UNKNOWN_WORKER_ERROR"
        assert "pytest worker failure" in (project.error_reason or "")
        assert project.quota_charged is False


def test_monitor_marks_missing_heartbeat_failed(
    client: TestClient,
    auth_headers: dict[str, str],
    sample_product_definition: dict,
    sample_market_config: dict,
) -> None:
    project_id = create_submitted_project(client, auth_headers, sample_product_definition, sample_market_config)
    task_id = run_project(client, auth_headers, project_id)
    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        project.status = "running"
        db.commit()
    get_redis_client().delete(f"simulation:heartbeat:{task_id}")

    result = monitor.scan_once(project_id=project_id)
    assert result["failed"] >= 1

    with SessionLocal() as db:
        project = db.get(SimulationProject, project_id)
        assert project is not None
        assert project.status == "failed"
        assert project.error_code == "WORKER_LOST"
        assert project.quota_charged is False


def test_multi_scheme_comparison_shape() -> None:
    snapshot = {
        "project_name": "pytest 多方案",
        "product_definition": {
            "mode": "multi_scheme",
            "active_scheme_id": "scheme_a",
            "schemes": [
                {
                    "scheme_id": "scheme_a",
                    "scheme_name": "基础款",
                    "product_name": "测试基础款",
                    "price_cny": 2999,
                    "specifications": {"电池": "4500mAh"},
                },
                {
                    "scheme_id": "scheme_b",
                    "scheme_name": "高端款",
                    "product_name": "测试高端款",
                    "price_cny": 4999,
                    "specifications": {"电池": "5500mAh", "屏幕": "OLED"},
                },
            ],
        },
        "market_config": {"target_crowd": "高端用户"},
    }
    aggregation = {
        "purchase_intent_avg": 0.7,
        "purchase_intent_distribution": {"buy": 1},
        "top_purchase_drivers": [],
        "top_purchase_blockers": [],
        "evidence_quality": {},
    }

    result = worker.build_scheme_comparison(snapshot, {"competitor_query": []}, [], [], aggregation, "pro")

    assert result is not None
    assert result["mode"] == "multi_scheme"
    assert len(result["scheme_results"]) == 2
    assert result["comparison_summary"]["best_scheme_id"] in {"scheme_a", "scheme_b"}
