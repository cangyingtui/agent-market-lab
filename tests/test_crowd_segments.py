from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.crowd_profile import canonicalize_market_crowds, crowd_profile_text, validate_crowd_segments
from app.export_service import crowd_profile_rows
from app.main import validate_market_crowds
from engine.agent_generator import generate_agents
from engine.aggregation import aggregate_results
from engine.chart_data import purchase_intent_rows
from engine.report_generator import build_fallback_report


pytestmark = pytest.mark.no_db


def crowd_segments(*ratios: int) -> list[dict]:
    return [
        {
            "name": f"客群{index + 1}",
            "ratio": ratio,
            "is_custom": False,
            "profile": {
                "price_sensitivity": "high" if index % 2 else "low",
                "feature_priorities": [f"偏好{index + 1}"],
            },
        }
        for index, ratio in enumerate(ratios)
    ]


def test_legacy_crowd_is_canonicalized_to_single_segment() -> None:
    market = canonicalize_market_crowds(
        {
            "target_crowd": "年轻白领",
            "crowd_profile": {"price_sensitivity": "medium", "feature_priorities": ["效率"]},
        }
    )

    assert market["crowd_segments"][0]["name"] == "年轻白领"
    assert market["crowd_segments"][0]["ratio"] == 100
    assert "占比:100%" in crowd_profile_text(market)


def test_new_crowd_segments_require_positive_integer_ratios_totaling_100() -> None:
    _, error = validate_crowd_segments({"crowd_segments": crowd_segments(60, 30)})
    assert error == "CROWD_RATIO_TOTAL_INVALID"

    _, error = validate_crowd_segments({"crowd_segments": crowd_segments(60, 40.5)})
    assert error == "CROWD_RATIO_INVALID"

    with pytest.raises(HTTPException) as exc_info:
        validate_market_crowds({"crowd_segments": crowd_segments(25, 25, 25, 25)}, "basic")
    assert exc_info.value.detail["code"] == "BASIC_CROWD_LIMIT"


def test_agents_expand_for_many_segments_and_keep_sample_weights() -> None:
    segments = crowd_segments(*([6] * 14), 16)
    snapshot = {
        "product_definition": {"product_name": "测试产品", "specifications": {"续航": "长"}},
        "market_config": {"crowd_segments": segments},
    }

    agents = generate_agents(snapshot, {}, count=8)["agents"]

    assert len(agents) == 15
    assert {agent["segment"] for agent in agents} == {segment["name"] for segment in segments}
    assert round(sum(agent["sample_weight"] for agent in agents), 6) == 1.0


def test_weighted_aggregation_changes_with_segment_ratio() -> None:
    agents = [
        {"agent_id": "agent_001", "segment": "高意愿", "sample_weight": 0.8, "price_sensitivity": "low"},
        {"agent_id": "agent_002", "segment": "低意愿", "sample_weight": 0.2, "price_sensitivity": "high"},
    ]
    decisions = [
        {"agent_id": "agent_001", "purchase_intent_score": 0.9, "decision": "buy"},
        {"agent_id": "agent_002", "purchase_intent_score": 0.1, "decision": "not_buy"},
    ]
    weighted_high = aggregate_results(agents, decisions, {}, {"market_config": {}})

    agents[0]["sample_weight"] = 0.2
    agents[1]["sample_weight"] = 0.8
    weighted_low = aggregate_results(agents, decisions, {}, {"market_config": {}})

    assert weighted_high["purchase_intent_avg"] == 0.74
    assert weighted_low["purchase_intent_avg"] == 0.26
    assert weighted_high["segment_summary"]["高意愿"]["ratio"] == 80.0


def test_basic_chart_and_fallback_report_keep_segment_breakdown() -> None:
    aggregation = {
        "purchase_intent_avg": 0.6,
        "segment_summary": {
            "年轻白领": {"avg_purchase_intent": 0.7, "count": 5, "ratio": 60, "weighted_contribution": 0.42},
            "育儿家庭": {"avg_purchase_intent": 0.45, "count": 3, "ratio": 40, "weighted_contribution": 0.18},
        },
    }
    rows = purchase_intent_rows(aggregation, "basic")
    assert [row["name"] for row in rows] == ["年轻白领", "育儿家庭"]
    assert rows[0]["ratio"] == 60

    report = build_fallback_report(
        {
            "product_definition": {"product_name": "测试产品"},
            "market_config": {"crowd_segments": crowd_segments(60, 40)},
        },
        {},
    )
    assert [item["ratio"] for item in report["target_segments"]] == [60, 40]

    export_rows = crowd_profile_rows(report)
    assert {row["客群"] for row in export_rows} == {"客群1", "客群2"}
    assert {row["占比"] for row in export_rows} == {"60%", "40%"}
