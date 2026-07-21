from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import delete, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    DistillCheckLog,
    ExportTask,
    QuotaLog,
    RagTraceLog,
    ShareToken,
    SimulationProject,
    SimulationTaskLog,
    UpgradeLog,
    User,
)
from app.redis_client import get_redis_client  # noqa: E402


TEST_PREFIXES = ("pytest_", "smoke_", "worker_", "e2e_", "e2e_u_")


def cleanup_redis(task_id: str | None, project_id: int | None = None) -> None:
    client = get_redis_client()
    if task_id:
        for queue_name in (settings.redis_basic_queue, settings.redis_pro_queue, settings.redis_task_queue):
            for raw_item in client.lrange(queue_name, 0, -1):
                if task_id in raw_item:
                    client.lrem(queue_name, 0, raw_item)
        client.delete(f"simulation:progress:{task_id}")
        client.delete(f"simulation:cancel:{task_id}")
        client.delete(f"simulation:heartbeat:{task_id}")
    if project_id:
        client.delete(f"simulation:project:{project_id}:running")


def main() -> int:
    with SessionLocal() as db:
        users = []
        for prefix in TEST_PREFIXES:
            users.extend(db.scalars(select(User).where(User.username.like(f"{prefix}%"))))
        user_ids = sorted({user.id for user in users})
        projects = list(db.scalars(select(SimulationProject).where(SimulationProject.user_id.in_(user_ids)))) if user_ids else []
        project_ids = [project.id for project in projects]
        task_ids = [project.task_id for project in projects if project.task_id]

        for project in projects:
            cleanup_redis(project.task_id, project.id)

        if project_ids:
            for model in (ExportTask, ShareToken, QuotaLog, DistillCheckLog, RagTraceLog, SimulationTaskLog):
                db.execute(delete(model).where(model.project_id.in_(project_ids)))
            db.execute(delete(SimulationProject).where(SimulationProject.id.in_(project_ids)))
        if user_ids:
            db.execute(delete(UpgradeLog).where(UpgradeLog.user_id.in_(user_ids)))
            db.execute(delete(QuotaLog).where(QuotaLog.user_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()

    print(
        {
            "deleted_users": len(user_ids),
            "deleted_projects": len(project_ids),
            "cleaned_task_ids": len(task_ids),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
