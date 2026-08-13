from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.custom_competitor_backfill import (  # noqa: E402
    custom_competitors_from_snapshot,
    enqueue_project_backfill,
)
from app.database import SessionLocal  # noqa: E402
from app.models import CustomCompetitorBackfillJob, SimulationProject, User  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="扫描历史仿真快照，将其中的自定义竞品加入低优先级复用队列",
    )
    parser.add_argument("--username", help="只扫描指定账号，例如 123@test")
    parser.add_argument("--project-id", action="append", type=int, dest="project_ids", help="只扫描指定项目，可重复")
    parser.add_argument("--apply", action="store_true", help="实际创建待办；默认只预览")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        stmt = select(SimulationProject).where(
            SimulationProject.config_snapshot.is_not(None),
            SimulationProject.snapshot_hash.is_not(None),
        )
        if args.project_ids:
            stmt = stmt.where(SimulationProject.id.in_(args.project_ids))
        if args.username:
            user = db.scalar(select(User).where(User.username == args.username))
            if user is None:
                print(json.dumps({"error": "user_not_found", "username": args.username}, ensure_ascii=False))
                return 2
            stmt = stmt.where(SimulationProject.user_id == user.id)

        projects = list(db.scalars(stmt.order_by(SimulationProject.id)))
        custom_projects = []
        enqueued = 0
        existing = 0
        custom_items = 0
        for project in projects:
            competitors = custom_competitors_from_snapshot(project.config_snapshot)
            if not competitors:
                continue
            custom_items += len(competitors)
            existing_job = db.scalar(
                select(CustomCompetitorBackfillJob).where(
                    CustomCompetitorBackfillJob.project_id == project.id,
                    CustomCompetitorBackfillJob.snapshot_hash == project.snapshot_hash,
                )
            )
            custom_projects.append(
                {
                    "project_id": project.id,
                    "project_name": project.project_name,
                    "custom_competitor_count": len(competitors),
                    "already_queued": existing_job is not None,
                }
            )
            if existing_job is not None:
                existing += 1
            elif args.apply:
                enqueue_project_backfill(db, project)
                enqueued += 1

        if args.apply:
            db.commit()
        else:
            db.rollback()

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry_run",
                "scanned_projects": len(projects),
                "custom_projects": len(custom_projects),
                "custom_competitors": custom_items,
                "enqueued": enqueued,
                "already_queued": existing,
                "projects": custom_projects,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
