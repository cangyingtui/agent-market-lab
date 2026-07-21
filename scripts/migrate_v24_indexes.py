from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import engine  # noqa: E402


INDEXES: dict[str, list[tuple[str, str]]] = {
    "simulation_projects": [
        ("idx_sim_projects_user_status_created", "(user_id, status, created_at)"),
        ("idx_sim_projects_user_updated", "(user_id, updated_at)"),
        ("idx_sim_projects_status_heartbeat", "(status, last_heartbeat_at)"),
        ("idx_sim_projects_status_started", "(status, started_at)"),
    ],
    "products": [
        ("idx_products_category_quality", "(category_id, quality_status, is_active)"),
        ("idx_products_category_price", "(category_id, price_cny)"),
        ("idx_products_name", "(product_name)"),
    ],
    "simulation_task_logs": [
        ("idx_task_logs_project_task_created", "(project_id, task_id, created_at)"),
    ],
    "rag_trace_logs": [
        ("idx_rag_trace_project_task_snapshot", "(project_id, task_id, snapshot_id)"),
    ],
    "distill_check_logs": [
        ("idx_distill_project_batch", "(project_id, validation_batch_id)"),
    ],
    "quota_logs": [
        ("idx_quota_user_project_created", "(user_id, project_id, created_at)"),
    ],
    "export_tasks": [
        ("idx_export_project_user_status", "(project_id, user_id, status)"),
    ],
    "share_tokens": [
        ("idx_share_token_expires", "(token_hash, expires_at)"),
    ],
}


def main() -> int:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, indexes in INDEXES.items():
            existing = {item["name"] for item in inspector.get_indexes(table)}
            for name, columns_sql in indexes:
                if name in existing:
                    print(f"skip {table}.{name}")
                    continue
                conn.execute(text(f"CREATE INDEX {name} ON {table} {columns_sql}"))
                print(f"created {table}.{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
