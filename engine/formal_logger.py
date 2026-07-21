from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR, settings
from app.time_utils import utc_now_iso, utc_now_naive


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE)
    return value.strip("_")[:80] or "scenario"


def current_run_dir() -> Path:
    env_dir = os.getenv("FORMAL_RUN_DIR")
    if env_dir:
        path = Path(env_dir)
        return path if path.is_absolute() else ROOT_DIR / path
    stamp = utc_now_naive().strftime("%Y%m%d_%H%M%S")
    return ROOT_DIR / "logs" / "formal_runs" / stamp


def compact(value: Any, max_chars: int = 6000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "chars": len(text), "preview": text[:max_chars]}


def write_formal_task_log(
    scenario_name: str,
    task_id: str,
    payload: dict[str, Any],
    run_dir: Path | None = None,
) -> str:
    directory = run_dir or current_run_dir()
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"{safe_name(scenario_name)}_{safe_name(task_id)}.json"
    record = {
        "scenario_name": scenario_name,
        "task_id": task_id,
        "created_at": utc_now_iso(),
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        **payload,
    }
    file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary = {
        "scenario_name": scenario_name,
        "task_id": task_id,
        "status": payload.get("status"),
        "is_fallback": payload.get("is_fallback", payload.get("report", {}).get("is_fallback")),
        "quality_warnings": payload.get("quality_warnings", payload.get("report", {}).get("quality_warnings", [])),
        "metrics": payload.get("metrics", payload.get("report", {}).get("metrics", {})),
        "log_path": str(file_path),
        "created_at": record["created_at"],
    }
    with (directory / "summary.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
    return str(file_path)
