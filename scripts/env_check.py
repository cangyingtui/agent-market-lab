from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402


def main() -> int:
    checks = {
        "database_url": settings.database_url,
        "redis_url": settings.redis_url,
        "enable_rag": settings.enable_rag,
        "rag_mode": settings.rag_mode,
        "faiss_index_exists": settings.resolve_path(settings.faiss_index_path).exists(),
        "faiss_metadata_exists": settings.resolve_path(settings.faiss_metadata_path).exists(),
        "embedding_model_configured": bool(settings.embedding_model),
        "embedding_api_key_configured": bool(settings.embedding_api_key),
        "embedding_base_may_not_support_embeddings": "api.deepseek.com" in settings.embedding_api_base,
        "enable_distill_check": settings.enable_distill_check,
        "distill_api_base_configured": bool(settings.distill_api_base),
        "distill_consistency_path": settings.distill_consistency_path,
        "distill_batch_size": settings.distill_batch_size,
        "distill_model_version": settings.distill_model_version,
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["faiss_index_exists"] and checks["faiss_metadata_exists"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
