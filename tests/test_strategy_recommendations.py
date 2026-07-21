from __future__ import annotations

import pytest

from app.strategy_recommendations import normalize_strategy_recommendations, strategy_recommendation_rows
from engine.report_generator import REPORT_KEYS, build_report_prompt, normalize_report


pytestmark = pytest.mark.no_db


def test_strategy_recommendations_normalize_strings_objects_and_aliases() -> None:
    rows = normalize_strategy_recommendations(
        [
            "突出核心卖点",
            {
                "name": "渠道聚焦",
                "steps": ["短视频展示", "门店体验"],
                "impact": "提升触达",
            },
            {"unexpected": {"value": "保留异常内容"}},
            None,
        ]
    )

    assert rows[0] == {"strategy": "突出核心卖点", "actions": [], "expected_impact": ""}
    assert rows[1] == {
        "strategy": "渠道聚焦",
        "actions": ["短视频展示", "门店体验"],
        "expected_impact": "提升触达",
    }
    assert "unexpected" in rows[2]["strategy"]
    assert len(rows) == 3


def test_strategy_recommendation_rows_are_export_friendly() -> None:
    rows = strategy_recommendation_rows(
        [{"strategy": "售后保障", "actions": ["延长保修", "上门服务"], "expected_impact": "减少顾虑"}]
    )

    assert rows == [{"策略": "售后保障", "执行动作": "延长保修；上门服务", "预期影响": "减少顾虑"}]


def test_report_prompt_requires_structured_strategy_recommendations() -> None:
    prompt = build_report_prompt({}, {})
    text = "\n".join(item["content"] for item in prompt)

    assert "strategy、actions、expected_impact" in text
    assert "actions 必须是字符串数组" in text


def test_normalize_report_stores_future_recommendations_as_objects() -> None:
    fallback = {key: [] for key in REPORT_KEYS}
    fallback["executive_summary"] = "fallback"
    fallback["pricing_analysis"] = {}
    report = normalize_report({"strategy_recommendations": ["突出续航"]}, fallback)

    assert report["strategy_recommendations"] == [
        {"strategy": "突出续航", "actions": [], "expected_impact": ""}
    ]
