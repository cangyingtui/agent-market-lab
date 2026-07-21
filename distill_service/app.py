from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from distill_service.inference import SentimentPredictor


app = FastAPI(title="Agentsim Distill Service", version="0.1.0")
predictor = SentimentPredictor()

EXPECTED_SENTIMENT = {
    "buy": "positive",
    "will_buy": "positive",
    "yes": "positive",
    "购买": "positive",
    "consider": "neutral",
    "considering": "neutral",
    "maybe": "neutral",
    "观望": "neutral",
    "not_buy": "negative",
    "not-buy": "negative",
    "reject": "negative",
    "no": "negative",
    "不购买": "negative",
}


class PredictRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    task_type: str = Field(default="sentiment", max_length=80)
    metadata: dict[str, Any] | None = None


class BatchPredictItem(BaseModel):
    id: str = Field(max_length=160)
    text: str = Field(default="", max_length=4000)
    metadata: dict[str, Any] | None = None


class BatchPredictRequest(BaseModel):
    items: list[BatchPredictItem] = Field(default_factory=list)
    task_type: str = Field(default="sentiment", max_length=80)


class ConsistencyRequest(BaseModel):
    snapshot: dict[str, Any] | None = None
    agents: list[dict[str, Any]] = Field(default_factory=list)
    purchase_decisions: list[dict[str, Any]] = Field(default_factory=list)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    sample_size: int = Field(default=16, ge=1, le=1000)
    validation_batch_id: str | None = Field(default=None, max_length=160)
    model_version: str | None = Field(default=None, max_length=120)


@app.get("/health")
def health() -> dict[str, Any]:
    status = predictor.health()
    status["enabled"] = True
    return status


@app.get("/v1/model-info")
def model_info() -> dict[str, Any]:
    status = predictor.health()
    return {
        "loaded": status["loaded"],
        "task_type": "sentiment_consistency",
        "labels": status["labels"],
        "model_version": status["model_version"],
        "model_dir": status["model_dir"],
        "error": status["error"],
    }


@app.post("/v1/predict")
def predict(req: PredictRequest) -> dict[str, Any]:
    try:
        result = predictor.predict(req.text)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["task_type"] = req.task_type
    result["metadata"] = req.metadata or {}
    return result


@app.post("/v1/batch-predict")
def batch_predict(req: BatchPredictRequest) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in req.items:
        try:
            prediction = predictor.predict(item.text)
            prediction["id"] = item.id
            prediction["metadata"] = item.metadata or {}
            results.append(prediction)
        except Exception as exc:
            results.append({"id": item.id, "status": "failed", "error": str(exc)})
    return {
        "results": results,
        "total": len(req.items),
        "model_version": predictor.model_version,
    }


def _normalized_decision_label(item: dict[str, Any]) -> str:
    raw = (
        item.get("agent_label")
        or item.get("decision")
        or item.get("purchase_decision")
        or item.get("label")
        or item.get("intent_label")
        or ""
    )
    return str(raw).strip().lower()


def _decision_text(item: dict[str, Any]) -> str:
    value = (
        item.get("distill_input_text")
        or item.get("input_text")
        or item.get("agent_reason")
        or item.get("reasoning")
        or item.get("reason")
        or item.get("rationale")
        or item.get("explanation")
        or ""
    )
    if value:
        return str(value)
    label = _normalized_decision_label(item) or "unknown"
    score = item.get("purchase_intent") or item.get("intent_score") or item.get("score")
    return f"agent_label={label}; score={score if score is not None else 'unknown'}"


def _judge_sample(item: dict[str, Any]) -> dict[str, Any]:
    text = _decision_text(item)
    prediction = predictor.predict(text)
    agent_label = _normalized_decision_label(item)
    expected = EXPECTED_SENTIMENT.get(agent_label)
    is_consistent = prediction["label"] == expected if expected else True
    if expected:
        judge_reason = f"expected {expected} from agent_label={agent_label}, got {prediction['label']}"
    else:
        judge_reason = f"agent_label={agent_label or 'unknown'} has no mapping; prediction recorded only"
    return {
        "sample_id": str(item.get("sample_id") or item.get("id") or item.get("agent_id") or uuid4().hex),
        "input_text": text,
        "agent_label": agent_label,
        "distill_label": prediction["label"],
        "confidence": prediction["confidence"],
        "is_consistent": is_consistent,
        "judge_reason": judge_reason,
        "model_version": prediction["model_version"],
    }


def _empty_response(req: ConsistencyRequest, *, status: str, warning: str = "") -> dict[str, Any]:
    return {
        "enabled": True,
        "status": status,
        "validation_batch_id": req.validation_batch_id or f"val_{uuid4().hex}",
        "checked_samples": 0,
        "consistent_count": 0,
        "inconsistent_count": 0,
        "consistency_score": None,
        "threshold": req.threshold,
        "average_confidence": None,
        "warning_level": "warning" if warning else "none",
        "warning": warning,
        "samples": [],
        "model_version": predictor.model_version,
    }


def consistency_check_impl(req: ConsistencyRequest) -> dict[str, Any]:
    if not predictor.loaded:
        return _empty_response(req, status="failed", warning=predictor.error or "model not loaded")
    decisions = req.purchase_decisions[: req.sample_size]
    if not decisions:
        return _empty_response(req, status="completed")

    samples = [_judge_sample(item) for item in decisions if isinstance(item, dict)]
    checked = len(samples)
    consistent = sum(1 for item in samples if item.get("is_consistent") is True)
    inconsistent = sum(1 for item in samples if item.get("is_consistent") is False)
    confidences = [
        float(item["confidence"])
        for item in samples
        if isinstance(item.get("confidence"), (int, float))
    ]
    score = consistent / checked if checked else None
    average_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None
    warning = "" if score is None or score >= req.threshold else "辅助模型一致性低于阈值，建议人工复核购买决策样本。"
    return {
        "enabled": True,
        "status": "completed",
        "validation_batch_id": req.validation_batch_id or f"val_{uuid4().hex}",
        "checked_samples": checked,
        "consistent_count": consistent,
        "inconsistent_count": inconsistent,
        "consistency_score": round(score, 4) if score is not None else None,
        "threshold": req.threshold,
        "average_confidence": average_confidence,
        "warning_level": "warning" if warning else "none",
        "warning": warning,
        "samples": samples,
        "model_version": predictor.model_version,
    }


@app.post("/v1/consistency-check")
def consistency_check_v1(req: ConsistencyRequest) -> dict[str, Any]:
    return consistency_check_impl(req)


@app.post("/consistency-check")
def consistency_check_legacy(req: ConsistencyRequest) -> dict[str, Any]:
    return consistency_check_impl(req)

