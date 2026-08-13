from __future__ import annotations

import copy

import pytest

from engine.chart_data import build_chart_data
from engine.commercial_model import MODEL_VERSION, audit_rows, enrich_strategy_recommendations, expert_matches
from engine.report_generator import build_report_prompt
from app.export_service import sanitize_report, sanitize_web_report


pytestmark = pytest.mark.no_db


def snapshot() -> dict:
    return {
        "commercial_model_version": MODEL_VERSION,
        "product_definition": {
            "product_name": "运动手环",
            "price_cny": 399,
            "params": [
                {"name": "续航", "weight": 5, "value": "21天"},
                {"name": "防水", "weight": 3, "value": "5ATM"},
                {"name": "材质", "weight": 2, "value": "铝合金"},
            ],
        },
        "market_config": {
            "target_crowd": "学生与初入职场价格敏感用户",
            "scenes": ["日常使用"],
            "strategies": ["内容种草策略", "场景解决方案策略", "买二送一"],
            "strategy_details": {
                "内容种草策略": {"channels": ["小红书"]},
                "场景解决方案策略": {"channels": ["电商平台"]},
                "买二送一": {"channels": ["电商平台"], "benefit": "买二送一"},
            },
        },
    }


def aggregation() -> dict:
    return {
        "purchase_intent_avg": 0.65,
        "top_purchase_drivers": [{"item": "续航", "count": 5}, {"item": "防水", "count": 2}],
    }


def test_new_model_differentiates_strategy_channel_and_parameter_results() -> None:
    chart = build_chart_data(snapshot(), {}, [], [], aggregation(), "pro")
    assert len({row["roi_raw"] for row in chart["strategy_roi"]}) == 3
    assert len({row["share"] for row in chart["channel_effect"]}) > 1
    assert [row["importance"] for row in chart["param_importance"]] == sorted(
        [row["importance"] for row in chart["param_importance"]], reverse=True
    )
    assert chart["differentiation_audit"]["strategy_roi"]["status"] == "distinct"
    assert chart["commercial_model_version"] == MODEL_VERSION


def test_price_sensitivity_uses_non_linear_curve_and_competitor_anchor() -> None:
    configured = snapshot()
    configured["market_config"]["competitors"] = [
        {"product_name": "竞品A", "brand": "A", "price_cny": 299, "specifications": {}},
        {"product_name": "竞品B", "brand": "B", "price_cny": 499, "specifications": {}},
    ]
    chart = build_chart_data(configured, {}, [], [], aggregation(), "pro")
    rows = chart["price_sensitivity"]
    intents = [row["intent"] for row in rows]
    first_differences = [round(intents[index + 1] - intents[index], 3) for index in range(len(intents) - 1)]
    assert len(set(first_differences)) > 2
    assert next(row for row in rows if row["multiplier"] == 1.0)["intent"] == 65.0
    assert all(row["curve_model"] == "asymmetric_logistic_v1" for row in rows)
    assert all(row["competitor_anchor_price_cny"] == 399.0 for row in rows)


def test_parameter_comparison_maps_raw_field_codes_instead_of_display_labels() -> None:
    configured = snapshot()
    configured["product_definition"]["params"] = [
        {"name": "氧流量（L/min）", "raw_name": "oxygen_flow", "weight": 1, "value": 10},
        {"name": "噪音（dB）", "raw_name": "noise", "weight": 1, "value": 45},
    ]
    configured["market_config"]["competitors"] = [
        {"product_name": "竞品A", "brand": "A", "price_cny": 399, "specifications": {"oxygen_flow": 2, "noise": 45}},
        {"product_name": "竞品B", "brand": "B", "price_cny": 499, "specifications": {"oxygen_flow": 3, "noise": 46}},
    ]
    chart = build_chart_data(configured, {}, [], [], {"purchase_intent_avg": 0.65}, "pro")
    rows = chart["param_importance"]
    assert len({row["importance_raw"] for row in rows}) == 2
    assert all(row["comparison_coverage_pct"] == 100 for row in rows)
    assert rows[0]["component_scores"]["competitor_difference"] > rows[1]["component_scores"]["competitor_difference"]


def test_professional_education_authority_and_service_strategies_use_distinct_priors() -> None:
    configured = snapshot()
    configured["market_config"]["strategies"] = ["专业科普", "医护背书", "售后承诺"]
    configured["market_config"]["strategy_details"] = {}
    chart = build_chart_data(configured, {}, [], [], aggregation(), "pro")
    rows = chart["strategy_roi"]
    assert [row["strategy_kind"] for row in rows] == ["content", "authority", "service"]
    assert len({row["roi_raw"] for row in rows}) == 3


def test_heavy_promotion_is_low_priority_without_high_scene_match() -> None:
    chart = build_chart_data(snapshot(), {}, [], [], aggregation(), "pro")
    promotion = next(row for row in chart["strategy_roi"] if row["name"] == "买二送一")
    assert promotion["recommendation_priority"] == "low"
    assert promotion["commercial_feasibility"] == "cautious"
    assert "cost_risk" not in promotion


def test_heavy_promotion_can_be_conditional_when_context_is_highly_matched() -> None:
    market = copy.deepcopy(snapshot()["market_config"])
    market["scenes"] = ["电商大促直播"]
    result = expert_matches("买二送一", market["strategy_details"]["买二送一"], market)
    assert result["highly_matched"] is True
    assert result["priority"] == "medium"


def test_complete_cost_input_can_prove_loss_risk() -> None:
    configured = snapshot()
    configured["market_config"]["strategy_details"]["买二送一"]["economics"] = {
        "gross_margin_pct": 20,
        "discount_pct": 33.3,
        "unit_promotion_cost_cny": 10,
        "total_budget_cny": 50000,
    }
    chart = build_chart_data(configured, {}, [], [], aggregation(), "pro")
    promotion = next(row for row in chart["strategy_roi"] if row["name"] == "买二送一")
    assert promotion["commercial_feasibility"] == "cautious"
    assert promotion["cost_risk_level"] == "high"
    assert promotion["margin_safety_pct"] < 0
    assert "单位贡献" in promotion["cost_risk"]
    assert chart["strategy_economics"]["买二送一"]["completeness_pct"] == 100


def test_same_input_is_deterministic_and_real_ties_are_explained() -> None:
    first = build_chart_data(snapshot(), {}, [], [], aggregation(), "pro")
    second = build_chart_data(snapshot(), {}, [], [], aggregation(), "pro")
    assert first["strategy_roi"] == second["strategy_roi"]
    audit = audit_rows([{"raw": 1.0}, {"raw": 1.0}], "raw", 0.05)
    assert audit["status"] == "tied"
    assert "未形成可解释差异" in audit["explanation"]


def test_expert_ranking_moves_unmatched_heavy_promotion_behind_preferred_strategy() -> None:
    ranked = enrich_strategy_recommendations(
        [
            {"strategy": "买二送一", "actions": [], "expected_impact": "短期转化"},
            {"strategy": "内容种草策略", "actions": [], "expected_impact": "建立认知"},
        ],
        snapshot(),
    )
    assert ranked[0]["strategy"] == "内容种草策略"
    assert ranked[-1]["recommendation_priority"] == "low"


def test_unselected_unmatched_heavy_promotion_is_not_auto_recommended() -> None:
    configured = snapshot()
    configured["market_config"]["strategies"] = ["内容种草策略"]
    ranked = enrich_strategy_recommendations(
        [
            {"strategy": "买一送一", "actions": [], "expected_impact": "短期转化"},
            {"strategy": "内容种草策略", "actions": [], "expected_impact": "建立认知"},
        ],
        configured,
    )
    assert [row["strategy"] for row in ranked] == ["内容种草策略"]


def test_legacy_snapshot_keeps_legacy_chart_algorithm() -> None:
    legacy = snapshot()
    legacy.pop("commercial_model_version")
    chart = build_chart_data(legacy, {}, [], [], aggregation(), "pro")
    assert "commercial_model_version" not in chart
    assert "differentiation_audit" not in chart
    assert chart["strategy_roi"][0]["roi"] == chart["strategy_roi"][1]["roi"]


def test_report_prompt_contains_expert_and_non_financial_constraints() -> None:
    text = "\n".join(message["content"] for message in build_report_prompt(snapshot(), {}))
    assert "高让利策略默认低优先级" in text
    assert "不得为了制造差异编造梯度" in text
    assert "不得将仿真 ROI 描述为真实财务收益" in text


def test_public_report_redacts_exact_cost_inputs() -> None:
    public = sanitize_report(
        {
            "strategy_economics": {"内容种草": {"gross_margin_pct": 35, "total_budget_cny": 50000}},
            "chart_data": {"strategy_roi": [{"name": "内容种草", "roi": 2.0, "margin_safety_pct": 12.0}]},
        },
        public=True,
    )
    assert "strategy_economics" not in public
    assert "margin_safety_pct" not in public["chart_data"]["strategy_roi"][0]
    assert public["chart_data"]["strategy_roi"][0]["roi"] == 2.0


def test_owner_web_report_keeps_strategy_economics() -> None:
    owner = sanitize_web_report(
        {
            "strategy_economics": {"内容种草": {"gross_margin_pct": 35, "total_budget_cny": 50000}},
            "chart_data": {"strategy_roi": [{"name": "内容种草", "roi": 2.0, "margin_safety_pct": 12.0}]},
        },
        public=False,
    )
    assert owner["strategy_economics"]["内容种草"]["gross_margin_pct"] == 35
    assert owner["chart_data"]["strategy_roi"][0]["margin_safety_pct"] == 12.0
