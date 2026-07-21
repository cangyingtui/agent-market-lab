from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import distill_service.app as distill_app


class FakePredictor:
    loaded = True
    model_version = "sentiment_student_test"
    error = ""

    def health(self) -> dict:
        return {
            "ok": True,
            "loaded": True,
            "status": "ok",
            "device": "cpu",
            "model_dir": "fake",
            "model_version": self.model_version,
            "labels": {0: "negative", 1: "neutral", 2: "positive"},
            "error": "",
        }

    def predict(self, text: str) -> dict:
        label = "positive" if "喜欢" in text or "愿意" in text else "negative"
        return {
            "label": label,
            "confidence": 0.91,
            "probabilities": {"negative": 0.05, "neutral": 0.04, "positive": 0.91},
            "model_version": self.model_version,
            "latency_ms": 1.0,
        }


@pytest.mark.no_db
def test_distill_service_predict_and_consistency(monkeypatch) -> None:
    monkeypatch.setattr(distill_app, "predictor", FakePredictor())
    client = TestClient(distill_app.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["loaded"] is True

    predict = client.post("/v1/predict", json={"text": "我愿意购买这个产品"})
    assert predict.status_code == 200
    assert predict.json()["label"] == "positive"

    consistency = client.post(
        "/v1/consistency-check",
        json={
            "threshold": 0.8,
            "sample_size": 2,
            "validation_batch_id": "pytest_batch",
            "purchase_decisions": [
                {"sample_id": "s1", "decision": "buy", "reason": "我愿意购买这个产品"},
                {"sample_id": "s2", "decision": "not_buy", "reason": "价格太高，不想买"},
            ],
        },
    )
    body = consistency.json()
    assert consistency.status_code == 200
    assert body["status"] == "completed"
    assert body["checked_samples"] == 2
    assert body["model_version"] == "sentiment_student_test"
    assert body["samples"][0]["is_consistent"] is True
