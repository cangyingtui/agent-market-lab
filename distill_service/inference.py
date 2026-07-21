from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = PROJECT_ROOT / "knowledge_model" / "sentiment"
DEFAULT_LABELS = {0: "negative", 1: "neutral", 2: "positive"}


class SentimentPredictor:
    """Lazy wrapper around a local sequence-classification student model."""

    def __init__(self, model_dir: str | None = None) -> None:
        self.model_dir = Path(model_dir or os.getenv("DISTILL_MODEL_DIR", str(DEFAULT_MODEL_DIR))).resolve()
        self.model_version = os.getenv("DISTILL_MODEL_VERSION", "sentiment_student_v1")
        self.max_length = int(os.getenv("DISTILL_MAX_LENGTH", "192"))
        self.loaded = False
        self.error = ""
        self.device = "cpu"
        self.label_map = self._load_label_map()
        self.tokenizer: Any = None
        self.model: Any = None
        self.torch: Any = None
        self._load_model_card()
        self._load()

    def _load_label_map(self) -> dict[int, str]:
        for name in ("label_mapping.json", "label_map.json"):
            path = self.model_dir / name
            if not path.exists():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            labels: dict[int, str] = {}
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if str(key).isdigit():
                        labels[int(key)] = str(value)
                    elif isinstance(value, int):
                        labels[value] = str(key)
            if labels:
                return labels
        return dict(DEFAULT_LABELS)

    def _load_model_card(self) -> None:
        path = self.model_dir / "model_card.json"
        if not path.exists():
            return
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(card, dict):
            self.model_version = str(card.get("model_version") or card.get("version") or self.model_version)

    def _load(self) -> None:
        if not self.model_dir.exists():
            self.error = f"model directory not found: {self.model_dir}"
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.torch = torch
            self.device = os.getenv("DISTILL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
            self.model = AutoModelForSequenceClassification.from_pretrained(str(self.model_dir))
            self.model.to(self.device)
            self.model.eval()
            self.loaded = True
            self.error = ""
        except Exception as exc:
            self.error = str(exc)
            self.loaded = False

    def health(self) -> dict[str, Any]:
        return {
            "ok": self.loaded,
            "loaded": self.loaded,
            "status": "ok" if self.loaded else "failed",
            "device": self.device,
            "model_dir": str(self.model_dir),
            "model_version": self.model_version,
            "labels": self.label_map,
            "error": self.error,
        }

    def predict(self, text: str) -> dict[str, Any]:
        if not self.loaded:
            raise RuntimeError(self.error or "model not loaded")
        started = time.perf_counter()
        inputs = self.tokenizer(
            text or "",
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=self.max_length,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            probs = self.torch.softmax(outputs.logits, dim=-1)[0].detach().cpu().tolist()
        pred_index = max(range(len(probs)), key=lambda index: probs[index])
        probabilities = {
            self.label_map.get(index, str(index)): float(prob)
            for index, prob in enumerate(probs)
        }
        return {
            "label": self.label_map.get(pred_index, str(pred_index)),
            "confidence": float(probs[pred_index]),
            "probabilities": probabilities,
            "model_version": self.model_version,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

