from __future__ import annotations

from engine.chart_data import build_chart_data


def _snapshot() -> dict:
    return {
        "product_definition": {
            "product_name": "测试智能手机",
            "brand": "测试品牌",
            "price_cny": 3999,
            "specifications": {"电池": "5000mAh", "屏幕": "OLED", "防水": "IP68"},
        },
        "market_config": {
            "target_crowd": "高端用户",
            "strategy": "差异化",
            "competitors": [
                {"id": 1, "product_name": "竞品 A", "brand": "竞品品牌", "price_cny": 3599, "specifications": {"电池": "4800mAh"}}
            ],
        },
    }


def _aggregation() -> dict:
    return {
        "purchase_intent_avg": 0.72,
        "top_purchase_drivers": [{"item": "电池", "count": 4}, {"item": "防水", "count": 2}],
        "segment_summary": {"高端用户": {"avg_purchase_intent": 0.78, "count": 6}},
    }


def test_chart_data_market_share_totals_100_and_contains_self() -> None:
    chart_data = build_chart_data(_snapshot(), {"product_competition": []}, [], [], _aggregation(), plan_type="pro")

    market_share = chart_data["market_share"]
    assert any(item["role"] == "self" for item in market_share)
    assert any(item["role"] == "competitor" for item in market_share)
    assert round(sum(item["share"] for item in market_share), 1) == 100.0


def test_basic_and_pro_chart_data_have_different_depth() -> None:
    basic = build_chart_data(_snapshot(), {"product_competition": []}, [], [], _aggregation(), plan_type="basic")
    pro = build_chart_data(_snapshot(), {"product_competition": []}, [], [], _aggregation(), plan_type="pro")

    assert basic["plan_type"] == "basic"
    assert pro["plan_type"] == "pro"
    assert "competitor_radar" not in basic
    assert "sensitivity_waterfall" not in basic
    assert "competitor_radar" in pro
    assert "sensitivity_waterfall" in pro


def test_pro_keeps_full_competitor_analysis_but_compacts_chart() -> None:
    snapshot = _snapshot()
    snapshot["market_config"]["competitors"] = [
        {"id": index, "product_name": f"竞品 {index}", "brand": "测试品牌", "price_cny": 3000 + index}
        for index in range(1, 16)
    ]

    chart_data = build_chart_data(snapshot, {"product_competition": []}, [], [], _aggregation(), plan_type="pro")

    assert chart_data["overview_metrics"]["competitor_count"] == 15
    assert len(chart_data["competitor_analysis"]) == 15
    assert any(item["name"] == "其他竞品汇总" for item in chart_data["market_share"])
    assert round(sum(item["share"] for item in chart_data["market_share"]), 1) == 100.0


def test_strategy_roi_accepts_string_strategy_list_for_pro() -> None:
    snapshot = _snapshot()
    snapshot["market_config"]["strategies"] = ["性价比策略", "场景解决方案策略"]

    chart_data = build_chart_data(snapshot, {"product_competition": []}, [], [], _aggregation(), plan_type="pro")

    strategy_roi = chart_data["strategy_roi"]
    assert [item["name"] for item in strategy_roi] == ["性价比策略", "场景解决方案策略"]
    assert all(item["roi"] > 0 for item in strategy_roi)


def test_strategy_roi_string_strategy_list_respects_basic_limit() -> None:
    snapshot = _snapshot()
    snapshot["market_config"]["strategies"] = ["性价比策略", "场景解决方案策略"]

    chart_data = build_chart_data(snapshot, {"product_competition": []}, [], [], _aggregation(), plan_type="basic")

    strategy_roi = chart_data["strategy_roi"]
    assert len(strategy_roi) == 1
    assert strategy_roi[0]["name"] == "性价比策略"


def test_strategy_roi_falls_back_when_strategy_list_has_no_valid_items() -> None:
    snapshot = _snapshot()
    snapshot["market_config"]["strategy"] = "差异化兜底"
    snapshot["market_config"]["strategies"] = [None, 123, []]

    chart_data = build_chart_data(snapshot, {"product_competition": []}, [], [], _aggregation(), plan_type="pro")

    strategy_roi = chart_data["strategy_roi"]
    assert len(strategy_roi) == 1
    assert strategy_roi[0]["name"] == "差异化兜底"
