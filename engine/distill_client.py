from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings

DEFAULT_CONSISTENCY_THRESHOLD = 0.8


def _warning_level(score: float | None, threshold: float) -> str:
    if score is None:
        return "info"
    if score >= threshold:
        return "none"
    if score >= threshold - 0.15:
        return "warning"
    return "critical"


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _configured_threshold(snapshot: dict[str, Any], override: float | None = None) -> float:
    if override is not None:
        return max(0.0, min(1.0, float(override)))
    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    value = (
        params.get("distill_consistency_threshold")
        or market.get("distill_consistency_threshold")
        or DEFAULT_CONSISTENCY_THRESHOLD
    )
    return max(0.0, min(1.0, _as_float(value, DEFAULT_CONSISTENCY_THRESHOLD)))


def _configured_sample_size(snapshot: dict[str, Any], override: int | None = None) -> int:
    if override is not None:
        return max(1, int(override))
    params = snapshot.get("simulation_params") if isinstance(snapshot.get("simulation_params"), dict) else {}
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    value = params.get("distill_sample_size") or market.get("distill_sample_size") or settings.distill_batch_size
    return max(1, _as_int(value, settings.distill_batch_size))


def _decision_label(decision: dict[str, Any]) -> str:
    raw = (
        decision.get("decision")
        or decision.get("purchase_decision")
        or decision.get("agent_label")
        or decision.get("label")
        or decision.get("intent_label")
        or "unknown"
    )
    label = str(raw).strip().lower()
    if label in {"buy", "购买", "yes", "true", "will_buy"}:
        return "buy"
    if label in {"consider", "观望", "considering", "maybe"}:
        return "consider"
    if label in {"not_buy", "not-buy", "不购买", "no", "false", "reject"}:
        return "not_buy"
    return label or "unknown"


def select_distill_samples(decisions: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    """Stratified round-robin sample across decision labels, preserving input order inside each label."""

    valid = [item for item in decisions if isinstance(item, dict)]
    if len(valid) <= sample_size:
        return valid

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in valid:
        groups[_decision_label(item)].append(item)

    preferred = ["buy", "consider", "not_buy"]
    labels = [label for label in preferred if label in groups]
    labels.extend(label for label in groups.keys() if label not in labels)

    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    while len(selected) < sample_size and labels:
        progressed = False
        for label in labels:
            bucket = groups[label]
            while bucket and id(bucket[0]) in seen:
                bucket.pop(0)
            if not bucket:
                continue
            item = bucket.pop(0)
            selected.append(item)
            seen.add(id(item))
            progressed = True
            if len(selected) >= sample_size:
                break
        if not progressed:
            break
    return selected


def _agents_for_decisions(agents: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decision_agent_ids = {
        str(item.get("agent_id"))
        for item in decisions
        if isinstance(item, dict) and item.get("agent_id") is not None
    }
    if not decision_agent_ids:
        return agents
    matched = [
        item
        for item in agents
        if isinstance(item, dict) and str(item.get("agent_id")) in decision_agent_ids
    ]
    return matched or agents


def _normalize_samples(samples: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(samples, 1):
        if not isinstance(item, dict):
            continue
        sample = dict(item)
        sample.setdefault("sample_id", sample.get("id") or sample.get("agent_id") or f"sample_{index}")
        if "agent_label" not in sample:
            sample["agent_label"] = sample.get("decision") or sample.get("expected_label") or sample.get("label")
        if "distill_label" not in sample:
            sample["distill_label"] = sample.get("predicted_label") or sample.get("label")
        normalized.append(sample)
    return normalized


def _normalize_result(
    result: dict[str, Any],
    *,
    sample_count: int,
    threshold: float,
    validation_batch_id: str,
    requested_sample_size: int,
    request_path: str,
) -> dict[str, Any]:
    samples = result.get("samples") or result.get("checks") or result.get("items") or []
    samples = _normalize_samples(samples if isinstance(samples, list) else [])
    result_threshold = _as_float(
        result.get("threshold") or result.get("distill_consistency_threshold"),
        threshold,
    )
    checked = _as_int(result.get("checked_samples") or len(samples) or sample_count, sample_count)
    consistent = result.get("consistent_count")
    inconsistent = result.get("inconsistent_count")
    if consistent is None and samples:
        consistent = sum(1 for item in samples if item.get("is_consistent") is True)
    if inconsistent is None and samples:
        inconsistent = sum(1 for item in samples if item.get("is_consistent") is False)
    consistent_int = _as_int(consistent, 0)
    inconsistent_int = _as_int(inconsistent, max(checked - consistent_int, 0) if checked else 0)
    raw_score = result.get("consistency_score")
    score = _as_float(raw_score, consistent_int / checked) if raw_score is not None and checked else (consistent_int / checked if checked else None)
    confidence_values = [
        _as_float(item.get("confidence"), 0.0)
        for item in samples
        if isinstance(item.get("confidence"), (int, float))
    ]
    avg_confidence = (
        _as_float(result.get("average_confidence"), 0.0)
        if isinstance(result.get("average_confidence"), (int, float))
        else round(sum(confidence_values) / len(confidence_values), 4)
        if confidence_values
        else None
    )
    warning_level = str(result.get("warning_level") or _warning_level(score, result_threshold))
    warning = str(result.get("warning") or "")
    if not warning and warning_level in {"warning", "critical"}:
        warning = "辅助模型一致性低于阈值，建议人工复核购买决策样本。"
    model_version = str(result.get("model_version") or settings.distill_model_version)
    return {
        "enabled": bool(result.get("enabled", True)),
        "status": str(result.get("status") or "completed"),
        "validation_batch_id": str(result.get("validation_batch_id") or validation_batch_id),
        "checked_samples": checked,
        "consistent_count": consistent_int,
        "inconsistent_count": inconsistent_int,
        "consistency_score": round(score, 4) if score is not None else None,
        "threshold": result_threshold,
        "average_confidence": avg_confidence,
        "warning_level": warning_level,
        "warning": warning,
        "samples": samples,
        "model_version": model_version,
        "sample_size": requested_sample_size,
        "request_path": request_path,
        "raw": result,
    }


def _disabled_result() -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "disabled",
        "validation_batch_id": None,
        "checked_samples": 0,
        "consistent_count": 0,
        "inconsistent_count": 0,
        "consistency_score": None,
        "threshold": DEFAULT_CONSISTENCY_THRESHOLD,
        "average_confidence": None,
        "warning_level": "info",
        "warning": "",
        "samples": [],
        "model_version": settings.distill_model_version,
        "sample_size": 0,
        "request_path": settings.distill_consistency_path,
        "message": "辅助模型复核当前关闭，主项目不会加载本地大模型依赖。",
    }


def _failed_result(
    exc: Exception,
    *,
    validation_batch_id: str,
    threshold: float,
    sample_size: int,
    request_path: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": "failed",
        "validation_batch_id": validation_batch_id,
        "checked_samples": 0,
        "consistent_count": 0,
        "inconsistent_count": 0,
        "consistency_score": None,
        "threshold": threshold,
        "average_confidence": None,
        "warning_level": "warning",
        "warning": "辅助模型服务调用失败，主仿真结果已保留。",
        "samples": [],
        "model_version": settings.distill_model_version,
        "sample_size": sample_size,
        "request_path": request_path,
        "error": str(exc),
    }


class DistillClient:
    """轻量 HTTP 客户端；真正的小模型服务单独部署。"""

    def __init__(self) -> None:
        self.base_url = settings.distill_api_base.rstrip("/")
        self.timeout = settings.distill_timeout_seconds
        self.consistency_path = settings.distill_consistency_path or "/consistency-check"
        if not self.consistency_path.startswith("/"):
            self.consistency_path = f"/{self.consistency_path}"
        self.headers = {}
        if settings.distill_api_key:
            self.headers["Authorization"] = f"Bearer {settings.distill_api_key}"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("DISTILL_API_BASE 未配置")
        url = f"{self.base_url}{path}"
        response = httpx.post(url, json=payload, headers=self.headers, timeout=self.timeout, trust_env=False)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("辅助模型服务响应必须是 JSON object")
        return data

    def health(self) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "message": "DISTILL_API_BASE 未配置"}
        response = httpx.get(f"{self.base_url}/health", headers=self.headers, timeout=self.timeout, trust_env=False)
        response.raise_for_status()
        data = response.json()
        health = data if isinstance(data, dict) else {"ok": True, "raw": data}
        health.setdefault("ok", True)
        return health

    def consistency_check(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._post(self.consistency_path, payload)


def build_distill_request(
    snapshot: dict[str, Any],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    threshold: float | None = None,
    sample_size: int | None = None,
    validation_batch_id: str | None = None,
) -> dict[str, Any]:
    request_threshold = _configured_threshold(snapshot, threshold)
    request_sample_size = _configured_sample_size(snapshot, sample_size)
    sampled_decisions = select_distill_samples(decisions, request_sample_size)
    sampled_agents = _agents_for_decisions(agents, sampled_decisions)
    return {
        "snapshot": snapshot,
        "agents": sampled_agents,
        "purchase_decisions": sampled_decisions,
        "threshold": request_threshold,
        "sample_size": request_sample_size,
        "validation_batch_id": validation_batch_id or f"val_{uuid4().hex}",
        "model_version": settings.distill_model_version,
        "sampling": {
            "strategy": "decision_label_round_robin",
            "requested_sample_size": request_sample_size,
            "input_decision_count": len(decisions),
            "sampled_decision_count": len(sampled_decisions),
            "sampled_agent_count": len(sampled_agents),
            "decision_labels": sorted({_decision_label(item) for item in sampled_decisions if isinstance(item, dict)}),
        },
    }


def run_distill_checks_if_enabled(
    snapshot: dict[str, Any],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    threshold: float | None = None,
    sample_size: int | None = None,
    validation_batch_id: str | None = None,
) -> dict[str, Any]:
    if not settings.enable_distill_check:
        return _disabled_result()

    client = DistillClient()
    request = build_distill_request(
        snapshot,
        agents,
        decisions,
        threshold=threshold,
        sample_size=sample_size,
        validation_batch_id=validation_batch_id,
    )
    try:
        result = client.consistency_check(request)
        result.setdefault("enabled", True)
        normalized = _normalize_result(
            result,
            sample_count=len(request["purchase_decisions"]),
            threshold=float(request["threshold"]),
            validation_batch_id=str(request["validation_batch_id"]),
            requested_sample_size=int(request["sample_size"]),
            request_path=client.consistency_path,
        )
        normalized["sampling"] = request["sampling"]
        return normalized
    except Exception as exc:
        failed = _failed_result(
            exc,
            validation_batch_id=str(request["validation_batch_id"]),
            threshold=float(request["threshold"]),
            sample_size=int(request["sample_size"]),
            request_path=client.consistency_path,
        )
        failed["sampling"] = request["sampling"]
        return failed


def debug_distill_check(
    snapshot: dict[str, Any],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    threshold: float | None = None,
    sample_size: int | None = None,
    validation_batch_id: str | None = None,
) -> dict[str, Any]:
    result = run_distill_checks_if_enabled(
        snapshot,
        agents,
        decisions,
        threshold=threshold,
        sample_size=sample_size,
        validation_batch_id=validation_batch_id,
    )
    client = DistillClient()
    health: dict[str, Any] | None = None
    if settings.enable_distill_check and settings.distill_api_base:
        try:
            health = client.health()
        except Exception as exc:
            health = {"ok": False, "error": str(exc)}
    result["debug"] = {
        "service_enabled": settings.enable_distill_check,
        "api_base_configured": bool(settings.distill_api_base),
        "request_path": client.consistency_path,
        "model_version": result.get("model_version") or settings.distill_model_version,
        "health": health,
        "sample_size": result.get("sample_size"),
        "checked_samples": result.get("checked_samples"),
    }
    return result
