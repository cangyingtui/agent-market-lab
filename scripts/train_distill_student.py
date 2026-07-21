from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402


LABELS = ["negative", "neutral", "positive"]
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
ID_TO_LABEL = {index: label for index, label in enumerate(LABELS)}
LABEL_TO_DECISION = {
    "positive": "buy",
    "neutral": "consider",
    "negative": "not_buy",
}
DECISION_TO_LABEL = {
    "buy": "positive",
    "will_buy": "positive",
    "购买": "positive",
    "yes": "positive",
    "consider": "neutral",
    "considering": "neutral",
    "maybe": "neutral",
    "观望": "neutral",
    "not_buy": "negative",
    "not-buy": "negative",
    "reject": "negative",
    "不购买": "negative",
    "no": "negative",
}
TEXT_KEYS = (
    "distill_input_text",
    "input_text",
    "agent_reason",
    "reasoning",
    "reason",
    "rationale",
    "explanation",
    "decision_reason",
    "decision_explanation",
)
DECISION_KEYS = ("decision", "purchase_decision", "agent_label", "label", "intent_label")
LABEL_GUIDANCE = {
    "positive": "明确愿意购买、认可价值、接受价格、主动推荐或表达强购买意愿。",
    "neutral": "态度观望、需要比较、预算/功能仍需权衡、暂时考虑但没有明确拒绝。",
    "negative": "明确不购买、价格/功能/信任/场景不匹配、拒绝或短期无购买计划。",
}


@dataclass
class DistillRecord:
    text: str
    decision_label: str
    source_path: str
    sample_id: str


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> str:
    return str(value)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_json_values(value: Any) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "purchase_decisions" and isinstance(item, list):
                found.append(item)
            found.extend(_iter_json_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_iter_json_values(item))
    return found


def _decision_label(item: dict[str, Any]) -> str:
    raw = next((item.get(key) for key in DECISION_KEYS if item.get(key)), "")
    return str(raw).strip().lower()


def _decision_text(item: dict[str, Any]) -> str:
    for key in TEXT_KEYS:
        value = item.get(key)
        if value:
            return str(value).strip()
    label = _decision_label(item) or "unknown"
    score = item.get("purchase_intent") or item.get("intent_score") or item.get("score")
    return f"agent_label={label}; score={score if score is not None else 'unknown'}"


def collect_distill_records(logs_root: Path, max_samples: int) -> list[DistillRecord]:
    records: list[DistillRecord] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(logs_root.rglob("*.json")):
        if any(part in {"exports", "test_runs"} for part in path.parts):
            continue
        data = _read_json(path)
        if data is None:
            continue
        for decisions in _iter_json_values(data):
            for index, item in enumerate(decisions, 1):
                if not isinstance(item, dict):
                    continue
                text = _decision_text(item)
                label = _decision_label(item)
                if not text or not label:
                    continue
                key = (text, label)
                if key in seen:
                    continue
                seen.add(key)
                records.append(
                    DistillRecord(
                        text=text[:2000],
                        decision_label=label,
                        source_path=str(path.relative_to(PROJECT_ROOT)),
                        sample_id=str(item.get("sample_id") or item.get("agent_id") or f"{path.stem}_{index}"),
                    )
                )
                if len(records) >= max_samples:
                    return records
    return records


def _openai_client() -> Any:
    if not settings.llm_api_key or settings.llm_api_key == "replace-this":
        raise RuntimeError("LLM_API_KEY is not configured for teacher labeling.")
    from openai import OpenAI

    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base or None,
        timeout=settings.llm_timeout_seconds,
    )


def _parse_teacher_response(content: str) -> tuple[str, float, str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(content[start : end + 1])
    label = str(data.get("label") or "").strip().lower()
    if label not in LABEL_TO_ID:
        raise ValueError(f"invalid teacher label: {label}")
    confidence = float(data.get("confidence") or 0.0)
    rationale = str(data.get("rationale") or "")
    return label, max(0.0, min(1.0, confidence)), rationale


def _json_from_model_content(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start_object = content.find("{")
        end_object = content.rfind("}")
        start_array = content.find("[")
        end_array = content.rfind("]")
        candidates: list[str] = []
        if 0 <= start_object < end_object:
            candidates.append(content[start_object : end_object + 1])
        if 0 <= start_array < end_array:
            candidates.append(content[start_array : end_array + 1])
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise


def _safe_completion(client: Any, messages: list[dict[str, str]], *, temperature: float) -> str:
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
        )
    return response.choices[0].message.content or "{}"


def _text_key(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def _normalize_labeled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, 1):
        label = str(row.get("label") or "").strip().lower()
        text = str(row.get("text") or "").strip()
        if label not in LABEL_TO_ID or not text:
            continue
        text = text[:2000]
        key = (_text_key(text), label)
        if key in seen:
            continue
        seen.add(key)
        item = dict(row)
        item["text"] = text
        item["label"] = label
        item["label_id"] = LABEL_TO_ID[label]
        item.setdefault("decision_label", LABEL_TO_DECISION[label])
        item.setdefault("expected_label", label)
        item.setdefault("sample_id", f"labeled_{index}")
        item.setdefault("source_path", "unknown")
        normalized.append(item)
    return normalized


def teacher_label_records(records: list[DistillRecord]) -> list[dict[str, Any]]:
    client = _openai_client()
    labeled: list[dict[str, Any]] = []
    system = (
        "You label Chinese product-market simulation purchase-decision reasons "
        "for a compact student model. Return JSON only."
    )
    for record in records:
        expected = DECISION_TO_LABEL.get(record.decision_label)
        prompt = {
            "task": "Classify the sentiment/intent implied by the decision reason.",
            "allowed_labels": LABELS,
            "decision_label": record.decision_label,
            "expected_mapping_hint": expected,
            "text": record.text,
            "output_schema": {"label": "positive|neutral|negative", "confidence": 0.0, "rationale": "short"},
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        content = _safe_completion(client, messages, temperature=0)
        label, confidence, rationale = _parse_teacher_response(content)
        labeled.append(
            {
                "text": record.text,
                "label": label,
                "label_id": LABEL_TO_ID[label],
                "confidence": confidence,
                "teacher_rationale": rationale,
                "decision_label": record.decision_label,
                "expected_label": expected,
                "sample_id": record.sample_id,
                "source_path": record.source_path,
            }
        )
    return labeled


def _parse_augmented_samples(content: str, expected_label: str) -> list[dict[str, Any]]:
    data = _json_from_model_content(content)
    if isinstance(data, dict):
        raw_samples = data.get("samples") or data.get("items") or data.get("data") or []
    else:
        raw_samples = data
    if not isinstance(raw_samples, list):
        raise ValueError("teacher augmentation response must contain a samples list")

    parsed: list[dict[str, Any]] = []
    for item in raw_samples:
        if isinstance(item, str):
            text = item
            label = expected_label
            confidence = 0.9
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("reason") or item.get("rationale") or "").strip()
            label = str(item.get("label") or expected_label).strip().lower()
            try:
                confidence = float(item.get("confidence") or 0.9)
            except (TypeError, ValueError):
                confidence = 0.9
        else:
            continue
        if label != expected_label or not text:
            continue
        parsed.append(
            {
                "text": text[:2000],
                "label": label,
                "label_id": LABEL_TO_ID[label],
                "confidence": max(0.0, min(1.0, confidence)),
                "teacher_rationale": "teacher_balanced_augmentation",
                "decision_label": LABEL_TO_DECISION[label],
                "expected_label": label,
                "source_path": "teacher_augmentation",
            }
        )
    return parsed


def balance_with_teacher_augmentation(
    seed_rows: list[dict[str, Any]],
    *,
    target_per_label: int,
    batch_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if target_per_label <= 0:
        return _normalize_labeled_rows(seed_rows)

    rows = _normalize_labeled_rows(seed_rows)
    if not rows:
        raise RuntimeError("Need at least one seed label before teacher augmentation.")

    random.seed(seed)
    client = _openai_client()
    seen_texts = {_text_key(str(row["text"])) for row in rows}
    system = (
        "You generate synthetic Chinese product-market simulation purchase-decision reasons "
        "for training a compact sentiment student model. Return JSON only."
    )

    for label in LABELS:
        attempts_without_progress = 0
        while sum(1 for row in rows if row["label"] == label) < target_per_label:
            current_count = sum(1 for row in rows if row["label"] == label)
            missing = target_per_label - current_count
            request_count = min(max(1, batch_size), missing + 5)
            examples = [
                row["text"]
                for row in rows
                if row["label"] == label
            ]
            random.shuffle(examples)
            prompt = {
                "task": "Generate diverse short purchase-decision reasons in Chinese.",
                "target_label": label,
                "decision_label": LABEL_TO_DECISION[label],
                "label_guidance": LABEL_GUIDANCE[label],
                "count": request_count,
                "constraints": [
                    "Each text must be 20-120 Chinese characters.",
                    "Use realistic consumer language for product-market simulation.",
                    "Vary product categories, price sensitivity, feature fit, trust, brand, usage scenario, and timing.",
                    "Do not copy examples verbatim.",
                    "Every sample must clearly match target_label.",
                ],
                "few_shot_examples": examples[:8],
                "output_schema": {
                    "samples": [
                        {
                            "text": "Chinese purchase-decision reason",
                            "label": label,
                            "confidence": 0.0,
                        }
                    ]
                },
            }
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ]
            content = _safe_completion(client, messages, temperature=0.7)
            candidates = _parse_augmented_samples(content, label)
            added = 0
            for candidate in candidates:
                if sum(1 for row in rows if row["label"] == label) >= target_per_label:
                    break
                key = _text_key(candidate["text"])
                if not key or key in seen_texts:
                    continue
                seen_texts.add(key)
                candidate["sample_id"] = f"aug_{label}_{sum(1 for row in rows if row['label'] == label) + 1:04d}"
                rows.append(candidate)
                added += 1
            attempts_without_progress = attempts_without_progress + 1 if added == 0 else 0
            if attempts_without_progress >= 5:
                raise RuntimeError(
                    f"Teacher augmentation stalled for label={label}; "
                    f"current={sum(1 for row in rows if row['label'] == label)}, target={target_per_label}."
                )

    return _normalize_labeled_rows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


class TextDataset:
    def __init__(self, rows: list[dict[str, Any]], tokenizer: Any, max_length: int) -> None:
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        import torch

        row = self.rows[index]
        encoded = self.tokenizer(
            str(row["text"]),
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(int(row["label_id"]), dtype=torch.long)
        return item


def _stratified_train_eval_split(
    rows: list[dict[str, Any]],
    *,
    eval_ratio: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["label"])].append(row)

    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    for label in LABELS:
        bucket = list(grouped.get(label, []))
        rng.shuffle(bucket)
        if len(bucket) <= 1:
            train_rows.extend(bucket)
            continue
        eval_count = max(1, int(round(len(bucket) * eval_ratio)))
        eval_count = min(eval_count, len(bucket) - 1)
        eval_rows.extend(bucket[:eval_count])
        train_rows.extend(bucket[eval_count:])

    rng.shuffle(train_rows)
    rng.shuffle(eval_rows)
    if not eval_rows and len(train_rows) > 1:
        eval_rows.append(train_rows.pop())
    return train_rows, eval_rows


def _classification_metrics(gold_ids: list[int], pred_ids: list[int]) -> dict[str, Any]:
    confusion = {
        actual: {predicted: 0 for predicted in LABELS}
        for actual in LABELS
    }
    for gold, pred in zip(gold_ids, pred_ids):
        actual_label = ID_TO_LABEL.get(int(gold), str(gold))
        pred_label = ID_TO_LABEL.get(int(pred), str(pred))
        if actual_label in confusion and pred_label in confusion[actual_label]:
            confusion[actual_label][pred_label] += 1

    per_label: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for label in LABELS:
        true_positive = confusion[label][label]
        predicted_positive = sum(confusion[actual][label] for actual in LABELS)
        actual_positive = sum(confusion[label][predicted] for predicted in LABELS)
        precision = true_positive / predicted_positive if predicted_positive else 0.0
        recall = true_positive / actual_positive if actual_positive else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        f1_values.append(f1)
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": actual_positive,
        }

    accuracy = (
        sum(1 for gold, pred in zip(gold_ids, pred_ids) if gold == pred) / len(gold_ids)
        if gold_ids
        else None
    )
    return {
        "eval_accuracy": round(accuracy, 4) if accuracy is not None else None,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4) if f1_values else None,
        "per_label": per_label,
        "confusion_matrix": confusion,
    }


def train_student_model(
    rows: list[dict[str, Any]],
    *,
    base_model: str,
    output_dir: Path,
    run_dir: Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    seed: int,
    overwrite: bool,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise RuntimeError(f"{output_dir} already exists and is not empty. Pass --overwrite to replace it.")
    if len(rows) < 3:
        raise RuntimeError("Need at least 3 labeled samples to train a student model.")

    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    random.seed(seed)
    torch.manual_seed(seed)
    rows = _normalize_labeled_rows(rows)
    train_rows, eval_rows = _stratified_train_eval_split(rows, eval_ratio=0.2, seed=seed)

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=len(LABELS),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
        ignore_mismatched_sizes=True,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    train_loader = DataLoader(TextDataset(train_rows, tokenizer, max_length), batch_size=batch_size, shuffle=True)
    eval_loader = DataLoader(TextDataset(eval_rows, tokenizer, max_length), batch_size=batch_size)

    model.train()
    losses: list[float] = []
    for _ in range(epochs):
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

    model.eval()
    gold_ids: list[int] = []
    pred_ids: list[int] = []
    with torch.no_grad():
        for batch in eval_loader:
            labels = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            preds = torch.argmax(logits, dim=-1)
            gold_ids.extend(int(item) for item in labels.detach().cpu().tolist())
            pred_ids.extend(int(item) for item in preds.detach().cpu().tolist())
    eval_metrics = _classification_metrics(gold_ids, pred_ids)

    temp_dir = run_dir / "student_model_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(temp_dir, safe_serialization=True)
    tokenizer.save_pretrained(temp_dir)
    metrics = {
        "model_version": settings.distill_model_version,
        "base_model": base_model,
        "sample_count": len(rows),
        "train_count": len(train_rows),
        "eval_count": len(eval_rows),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "device": device,
        **eval_metrics,
        "train_loss_last": losses[-1] if losses else None,
        "label_distribution": {label: sum(1 for row in rows if row["label"] == label) for label in LABELS},
        "train_label_distribution": {label: sum(1 for row in train_rows if row["label"] == label) for label in LABELS},
        "eval_label_distribution": {label: sum(1 for row in eval_rows if row["label"] == label) for label in LABELS},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (temp_dir / "label_mapping.json").write_text(json.dumps(ID_TO_LABEL, ensure_ascii=False, indent=2), encoding="utf-8")
    (temp_dir / "model_card.json").write_text(
        json.dumps(
            {
                "model_version": metrics["model_version"],
                "task_type": "sentiment_consistency",
                "labels": LABELS,
                "teacher_model": settings.llm_model,
                "notes": "Student model for auxiliary purchase-decision consistency checks.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (temp_dir / "training_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    if output_dir.exists() and overwrite:
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(temp_dir), str(output_dir))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Teacher-label and train the local distill student model.")
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--output-dir", default="knowledge_model/sentiment")
    parser.add_argument("--labels-jsonl", default=None, help="Reuse an existing teacher-label JSONL instead of calling the teacher API.")
    parser.add_argument("--max-samples", type=int, default=120)
    parser.add_argument("--balance-target-per-label", type=int, default=0, help="Teacher-augment each label to this target count.")
    parser.add_argument("--augment-batch-size", type=int, default=25, help="Synthetic samples requested per teacher augmentation call.")
    parser.add_argument("--balanced-labels-jsonl", default=None, help="Where to write balanced teacher labels JSONL.")
    parser.add_argument("--base-model", default=settings.student_base_model)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else PROJECT_ROOT / "logs" / "distill_training" / _now_id()
    if not run_dir.is_absolute():
        run_dir = PROJECT_ROOT / run_dir
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if args.labels_jsonl:
        labels_path = Path(args.labels_jsonl)
        if not labels_path.is_absolute():
            labels_path = PROJECT_ROOT / labels_path
        labeled = read_jsonl(labels_path)
    else:
        records = collect_distill_records(PROJECT_ROOT / args.logs_root, max(1, args.max_samples))
        if not records:
            raise RuntimeError("No purchase_decisions were found in logs for teacher labeling.")
        labeled = teacher_label_records(records)
        labels_path = run_dir / "teacher_labels.jsonl"
        write_jsonl(labels_path, labeled)

    balanced_path: Path | None = None
    if args.balance_target_per_label > 0:
        labeled = balance_with_teacher_augmentation(
            labeled,
            target_per_label=args.balance_target_per_label,
            batch_size=args.augment_batch_size,
            seed=args.seed,
        )
        balanced_path = Path(args.balanced_labels_jsonl) if args.balanced_labels_jsonl else run_dir / "teacher_labels_balanced.jsonl"
        if not balanced_path.is_absolute():
            balanced_path = PROJECT_ROOT / balanced_path
        write_jsonl(balanced_path, labeled)

    metrics = train_student_model(
        labeled,
        base_model=args.base_model,
        output_dir=output_dir,
        run_dir=run_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "training_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "output_dir": str(output_dir),
                "run_dir": str(run_dir),
                "labels_path": str(labels_path),
                "balanced_labels_path": str(balanced_path) if balanced_path else None,
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
