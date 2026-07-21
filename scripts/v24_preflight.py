from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from engine.distill_client import DistillClient, run_distill_checks_if_enabled  # noqa: E402
from knowledge_model.rag_service import get_rag_service  # noqa: E402
from scripts.check_services import check_mysql, check_redis  # noqa: E402


def http_check(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True, trust_env=False)
        return {
            "ok": response.status_code < 500,
            "status_code": response.status_code,
            "url": url,
        }
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def rag_check() -> dict[str, Any]:
    try:
        status = get_rag_service(force_reload=True).status()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    dim_ok = True
    if status.get("embedding_configured"):
        dim_ok = status.get("index_dim") == status.get("embedding_dim")
    return {
        "ok": bool(status.get("metadata_matches_index") and dim_ok),
        **status,
    }


def distill_check(*, run_sample: bool = False) -> dict[str, Any]:
    if not settings.enable_distill_check:
        return {"ok": True, "enabled": False, "status": "disabled"}
    if not settings.distill_api_base:
        return {"ok": False, "enabled": True, "status": "missing_DISTILL_API_BASE"}
    client = DistillClient()
    try:
        health = client.health()
        health_ok = bool(health.get("ok", True))
    except Exception as exc:
        health = {"ok": False, "error": str(exc)}
        health_ok = False
    sample_result: dict[str, Any] | None = None
    sample_ok = True
    if run_sample and health_ok:
        sample_result = run_distill_checks_if_enabled(
            {"project_name": "v24_preflight", "simulation_params": {"distill_sample_size": 1}},
            [{"agent_id": "preflight_agent", "segment": "debug"}],
            [{"agent_id": "preflight_agent", "decision": "consider", "reason": "preflight sample"}],
            sample_size=1,
            validation_batch_id="preflight",
        )
        sample_ok = sample_result.get("status") == "completed"
    result = {
        "ok": bool(health_ok and sample_ok),
        "enabled": True,
        "api_base": settings.distill_api_base,
        "request_path": client.consistency_path,
        "model_version": settings.distill_model_version,
        "batch_size": settings.distill_batch_size,
        "health": health,
    }
    if sample_result is not None:
        result["sample_check"] = {
            "status": sample_result.get("status"),
            "checked_samples": sample_result.get("checked_samples"),
            "consistency_score": sample_result.get("consistency_score"),
            "warning_level": sample_result.get("warning_level"),
            "error": sample_result.get("error"),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Agentsim v2.4 local preflight and debug status check")
    parser.add_argument("--require-web", action="store_true", help="Fail if API or frontend URLs are not reachable")
    parser.add_argument("--require-distill", action="store_true", help="Fail if external distill service is disabled or unreachable")
    args = parser.parse_args()

    mysql_ok, mysql_message = check_mysql()
    redis_ok, redis_message = check_redis()
    api = http_check(f"{settings.public_base_url.rstrip('/')}/health")
    frontend = http_check(settings.frontend_base_url.rstrip("/"))
    queue = (
        http_check(f"{settings.public_base_url.rstrip('/')}/api/debug/queue/status")
        if api.get("ok")
        else {"ok": False, "skipped": True, "reason": "api_unreachable"}
    )
    result = {
        "core": {
            "mysql": {"ok": mysql_ok, "message": mysql_message},
            "redis": {"ok": redis_ok, "message": redis_message},
            "rag": rag_check(),
        },
        "web": {
            "api_health": api,
            "frontend": frontend,
            "queue_debug": queue,
        },
        "distill": distill_check(run_sample=args.require_distill),
        "commands": {
            "api": r".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload",
            "frontend": "cd frontend; npm.cmd run dev",
            "worker": r".\.venv\Scripts\python.exe -m engine.worker",
            "monitor": r".\.venv\Scripts\python.exe -m engine.monitor",
            "acceptance": r".\.venv\Scripts\python.exe scripts\run_frontend_scenarios.py --limit 1 --run-worker",
        },
    }

    core_ok = mysql_ok and redis_ok and bool(result["core"]["rag"].get("ok"))
    web_ok = bool(api.get("ok") and frontend.get("ok")) if args.require_web else True
    distill_ok = bool(result["distill"].get("ok") and result["distill"].get("enabled")) if args.require_distill else bool(result["distill"].get("ok"))
    result["ok"] = bool(core_ok and web_ok and distill_ok)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
