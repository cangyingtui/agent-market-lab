from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import SystemFeatureFlag  # noqa: E402


DEFAULT_FLAGS = [
    {
        "flag_name": "enable_rag",
        "is_enabled": settings.enable_rag,
        "config_json": {
            "mode": settings.rag_mode,
            "top_k": settings.rag_top_k,
            "faiss_index_path": settings.faiss_index_path,
            "faiss_metadata_path": settings.faiss_metadata_path,
        },
        "description": "Enable FAISS-based retrieval augmented generation.",
    },
    {
        "flag_name": "enable_distill_check",
        "is_enabled": settings.enable_distill_check,
        "config_json": {
            "api_base_configured": bool(settings.distill_api_base),
            "consistency_path": settings.distill_consistency_path,
            "batch_size": settings.distill_batch_size,
            "model_version": settings.distill_model_version,
        },
        "description": "Enable external distilled-model consistency checks over HTTP.",
    },
    {
        "flag_name": "enable_debug_api",
        "is_enabled": settings.enable_debug_api,
        "config_json": {"app_env": settings.app_env},
        "description": "Expose development-only debug endpoints.",
    },
    {
        "flag_name": "task_retry_policy",
        "is_enabled": True,
        "config_json": {
            "max_retry_times": settings.max_retry_times,
            "task_timeout_seconds": settings.task_timeout_seconds,
            "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
        },
        "description": "Worker retry, timeout, and heartbeat defaults.",
    },
    {
        "flag_name": "queue_priority",
        "is_enabled": True,
        "config_json": {
            "default_queue": settings.redis_task_queue,
            "pro_queue": settings.redis_pro_queue,
            "basic_queue": settings.redis_basic_queue,
        },
        "description": "Redis queue names for default/basic/pro simulation tasks.",
    },
]


def main() -> int:
    created = 0
    updated = 0

    with SessionLocal() as db:
        for item in DEFAULT_FLAGS:
            flag = db.scalar(
                select(SystemFeatureFlag).where(SystemFeatureFlag.flag_name == item["flag_name"])
            )
            if flag is None:
                db.add(SystemFeatureFlag(**item))
                created += 1
                continue

            flag.is_enabled = item["is_enabled"]
            flag.config_json = item["config_json"]
            flag.description = item["description"]
            updated += 1
        db.commit()

    print(f"Seeded feature flags: created={created}, updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
