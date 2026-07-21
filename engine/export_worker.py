from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.export_service import write_export_file  # noqa: E402
from app.models import ExportTask, SimulationProject  # noqa: E402
from app.redis_client import get_redis_client, redis_json_set  # noqa: E402
from app.task_keys import export_progress_key, heavy_resource_lock_key  # noqa: E402
from app.time_utils import utc_now_iso  # noqa: E402


EXPORT_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def export_heartbeat(status: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"worker_id": EXPORT_WORKER_ID, "status": status, "updated_at": utc_now_iso()}
    if extra:
        payload.update({key: value for key, value in extra.items() if value is not None})
    redis_json_set(
        f"simulation:export-worker:{EXPORT_WORKER_ID}:heartbeat",
        payload,
        ex=max(settings.redis_heartbeat_ttl_seconds * 4, 60),
    )


def update_export_progress(export_task_id: int, status: str, message: str, extra: dict[str, Any] | None = None) -> None:
    payload = {
        "export_task_id": export_task_id,
        "status": status,
        "message": message,
        "updated_at": utc_now_iso(),
    }
    if extra:
        payload.update(extra)
    redis_json_set(export_progress_key(export_task_id), payload, ex=settings.redis_progress_expire_seconds)
    export_heartbeat(status, {"export_task_id": export_task_id})


def acquire_heavy_resource_lock(export_task_id: int) -> str:
    client = get_redis_client()
    owner = f"export:{export_task_id}"
    while not client.set(heavy_resource_lock_key(), owner, nx=True, ex=settings.heavy_resource_lock_ttl_seconds):
        update_export_progress(export_task_id, "queued", "正在等待系统资源，稍后自动生成 PDF")
        time.sleep(5)
    return owner


def release_heavy_resource_lock(owner: str | None) -> None:
    if not owner:
        return
    client = get_redis_client()
    lock_key = heavy_resource_lock_key()
    if client.get(lock_key) == owner:
        client.delete(lock_key)


def parse_task(raw: Any) -> dict[str, Any] | None:
    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def process_export_task(payload: dict[str, Any]) -> None:
    export_task_id = int(payload["export_task_id"])
    owner: str | None = None
    with SessionLocal() as db:
        task = db.get(ExportTask, export_task_id)
        if task is None:
            update_export_progress(export_task_id, "failed", "导出任务不存在")
            return
        if task.status == "completed":
            update_export_progress(export_task_id, "completed", "PDF 已生成", {"download_url": task.download_url})
            return
        project = db.get(SimulationProject, task.project_id)
        if project is None or project.status != "completed" or not project.result_data:
            task.status = "failed"
            task.error_reason = "报告尚未生成，无法导出 PDF"
            db.commit()
            update_export_progress(export_task_id, "failed", task.error_reason)
            return
        try:
            update_export_progress(export_task_id, "queued", "PDF 已进入生成队列")
            owner = acquire_heavy_resource_lock(export_task_id)
            task.status = "processing"
            task.error_reason = None
            db.commit()
            update_export_progress(export_task_id, "processing", "PDF生成中，请稍后")
            write_export_file(task, project)
            db.commit()
            db.refresh(task)
            update_export_progress(export_task_id, "completed", "PDF 已生成", {"download_url": task.download_url})
        except Exception as exc:
            db.rollback()
            task = db.get(ExportTask, export_task_id)
            if task is not None:
                task.status = "failed"
                task.error_reason = str(exc)
                db.commit()
            update_export_progress(export_task_id, "failed", str(exc))
        finally:
            release_heavy_resource_lock(owner)
            export_heartbeat("idle")


def pop_export_task(timeout: int) -> dict[str, Any] | None:
    export_heartbeat("waiting", {"queue": settings.redis_export_queue})
    result = get_redis_client().blpop([settings.redis_export_queue], timeout=timeout)
    if result is None:
        export_heartbeat("idle", {"queue": settings.redis_export_queue})
        return None
    _, raw = result
    return parse_task(raw)


def run_loop(once: bool, timeout: int) -> int:
    while True:
        payload = pop_export_task(timeout)
        if payload is None:
            if once:
                return 0
            continue
        process_export_task(payload)
        if once:
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 导出 Worker")
    parser.add_argument("--once", action="store_true", help="只消费一个导出任务后退出")
    parser.add_argument("--timeout", type=int, default=5, help="等待导出任务的秒数")
    args = parser.parse_args()
    return run_loop(once=args.once, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
