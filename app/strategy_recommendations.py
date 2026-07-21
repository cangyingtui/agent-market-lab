from __future__ import annotations

import json
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    return ""


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        text = _text(data.get(key))
        if text:
            return text
    return ""


def _actions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := _text(item))]
    text = _text(value)
    return [text] if text else []


def _fallback_text(value: Any) -> str:
    text = _text(value)
    if text:
        return text
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def normalize_strategy_recommendations(value: Any) -> list[dict[str, Any]]:
    raw_items = value if isinstance(value, list) else [value] if value not in (None, "") else []
    rows: list[dict[str, Any]] = []
    for item in raw_items:
        if item in (None, ""):
            continue
        if isinstance(item, dict):
            strategy = _first_text(item, "strategy", "name", "title", "recommendation", "summary")
            actions = _actions(
                item.get("actions")
                or item.get("action_items")
                or item.get("steps")
                or item.get("action")
            )
            expected_impact = _first_text(item, "expected_impact", "impact", "expected_result", "result")
            if not strategy:
                strategy = _fallback_text(item)
        else:
            strategy = _fallback_text(item)
            actions = []
            expected_impact = ""
        if strategy:
            rows.append(
                {
                    "strategy": strategy,
                    "actions": actions,
                    "expected_impact": expected_impact,
                }
            )
    return rows


def strategy_recommendation_rows(value: Any) -> list[dict[str, str]]:
    return [
        {
            "策略": item["strategy"],
            "执行动作": "；".join(item["actions"]),
            "预期影响": item["expected_impact"],
        }
        for item in normalize_strategy_recommendations(value)
    ]
