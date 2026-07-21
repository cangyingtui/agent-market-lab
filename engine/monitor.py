from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import QuotaLog, SimulationProject, SimulationTaskLog, User  # noqa: E402
from app.redis_client import get_redis_client, redis_json_set  # noqa: E402
from app.runtime_status import (  # noqa: E402
    REPORT_WAITING_STAGE,
    REPORT_WAITING_STATUS,
    format_utc_iso,
    report_wait_progress_extra,
    report_wait_progress_percent,
    report_wait_remaining_seconds,
)
from app.task_keys import progress_key, project_lock_key, project_progress_key  # noqa: E402
from app.time_utils import utc_now_iso, utc_now_naive  # noqa: E402


def rollback_quota_if_needed(db, project: SimulationProject, task_id: str, reason: str) -> None:
    if not project.quota_charged:
        return
    user = db.get(User, project.user_id)
    if user is None or user.plan_type == "pro":
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


def fail_project(db, project: SimulationProject, task_id: str, error_code: str, message: str) -> None:
    project.status = "failed"
    project.error_code = error_code
    project.error_reason = message
    project.completed_at = utc_now_naive()
    rollback_quota_if_needed(db, project, task_id, message)
    db.add(
        SimulationTaskLog(
            project_id=project.id,
            task_id=task_id,
            snapshot_id=project.snapshot_hash,
            stage="monitor",
            log_level="error",
            message=message,
            detail_json={"error_code": error_code},
        )
    )
    db.commit()
    redis_json_set(
        progress_key(task_id),
        payload := {
            "task_id": task_id,
            "project_id": project.id,
            "status": "failed",
            "percent": 100,
            "stage": "monitor",
            "message": message,
            "updated_at": utc_now_iso(),
            "error_code": error_code,
        },
        ex=settings.redis_progress_expire_seconds,
    )
    redis_json_set(project_progress_key(project.id), payload, ex=settings.redis_progress_expire_seconds)


def report_waiting_payload(project: SimulationProject) -> dict[str, object]:
    extra = report_wait_progress_extra(project.result_data or {})
    return {
        "task_id": project.task_id,
        "project_id": project.id,
        "status": REPORT_WAITING_STATUS,
        "percent": report_wait_progress_percent(project.result_data or {}),
        "stage": REPORT_WAITING_STAGE,
        "message": "报告正在生成，请稍后",
        "updated_at": utc_now_iso(),
        "report_waiting": True,
        "created_at": format_utc_iso(project.submitted_at) if project.submitted_at else None,
        "estimated_start_at": format_utc_iso(project.started_at) if project.started_at else extra.get("report_wait_started_at"),
        "target_duration_seconds": extra.get("report_wait_target_seconds"),
        **extra,
    }


def promote_report_waiting_projects(db, project_id: int | None = None) -> dict[str, int]:
    promoted = 0
    waiting = 0
    stmt = select(SimulationProject).where(SimulationProject.status == REPORT_WAITING_STATUS)
    if project_id is not None:
        stmt = stmt.where(SimulationProject.id == project_id)
    for project in db.scalars(stmt):
        waiting += 1
        if not project.task_id:
            continue
        remaining = report_wait_remaining_seconds(project.result_data or {})
        if remaining > 0:
            payload = report_waiting_payload(project)
            redis_json_set(progress_key(project.task_id), payload, ex=settings.redis_progress_expire_seconds)
            redis_json_set(project_progress_key(project.id), payload, ex=settings.redis_progress_expire_seconds)
            continue
        project.status = "completed"
        project.completed_at = utc_now_naive()
        project.last_heartbeat_at = utc_now_naive()
        db.add(
            SimulationTaskLog(
                project_id=project.id,
                task_id=project.task_id,
                snapshot_id=project.snapshot_hash,
                stage="completed",
                log_level="info",
                message="报告生成完成",
                detail_json={"promoted_from": REPORT_WAITING_STATUS},
            )
        )
        db.commit()
        payload = {
            "task_id": project.task_id,
            "project_id": project.id,
            "status": "completed",
            "percent": 100,
            "stage": "completed",
            "message": "任务已完成",
            "updated_at": utc_now_iso(),
            "completed_at": utc_now_iso(),
            "remaining_seconds": 0,
            "report_waiting": False,
        }
        redis_json_set(progress_key(project.task_id), payload, ex=settings.redis_progress_expire_seconds)
        redis_json_set(project_progress_key(project.id), payload, ex=settings.redis_progress_expire_seconds)
        promoted += 1
    return {"report_waiting": waiting, "report_promoted": promoted}


def scan_once(project_id: int | None = None) -> dict[str, int]:
    client = get_redis_client()
    checked = 0
    failed = 0
    with SessionLocal() as db:
        report_wait_result = promote_report_waiting_projects(db, project_id=project_id)
        keys = [project_lock_key(project_id)] if project_id is not None else client.scan_iter("simulation:project:*:running", count=200)
        for key in keys:
            checked += 1
            key_text = key.decode("utf-8", errors="ignore") if isinstance(key, bytes) else str(key)
            raw_task_id = client.get(key_text)
            if not raw_task_id:
                continue
            task_id = raw_task_id.decode("utf-8", errors="ignore") if isinstance(raw_task_id, bytes) else str(raw_task_id)
            try:
                project_id = int(key_text.split(":")[2])
            except (IndexError, ValueError):
                continue
            project = db.get(SimulationProject, project_id)
            if project is None:
                client.delete(key_text)
                continue
            if project.status != "running":
                if project.status == "submitted" and str(project.task_id or "") == task_id:
                    continue
                client.delete(key_text)
                continue
            heartbeat_exists = client.exists(f"simulation:heartbeat:{task_id}")
            timed_out = False
            if project.started_at:
                elapsed = (utc_now_naive() - project.started_at).total_seconds()
                timed_out = elapsed > settings.task_timeout_seconds
            if not heartbeat_exists:
                fail_project(db, project, task_id, "WORKER_LOST", "Worker 心跳丢失，任务已标记失败")
                client.delete(key_text)
                failed += 1
            elif timed_out:
                fail_project(db, project, task_id, "TASK_TIMEOUT", "任务运行超时，已标记失败")
                client.delete(key_text)
                client.delete(f"simulation:heartbeat:{task_id}")
                failed += 1
    return {"checked": checked, "failed": failed, **report_wait_result}


def run_loop(once: bool, interval: int) -> int:
    while True:
        scan_once()
        if once:
            return 0
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="产品市场仿真 Worker 监控器")
    parser.add_argument("--once", action="store_true", help="只扫描一次后退出")
    parser.add_argument("--interval", type=int, default=5, help="持续运行时的扫描间隔秒数")
    args = parser.parse_args()
    return run_loop(once=args.once, interval=args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
