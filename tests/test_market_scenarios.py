from __future__ import annotations

import pytest

from engine.chart_data import build_chart_data, collect_competitors, configured_competitors, price_competitiveness, price_data_gaps
from engine.maut_model import adaptive_thresholds, brand_loyalty_score, build_decision_model_summary, decision_weight_profile
from engine.propagation_funnel import build_propagation_funnel
from scripts.migrate_product_prices_20260728 import load_actions


pytestmark = pytest.mark.no_db


def _snapshot() -> dict:
    return {
        "product_definition": {"product_name": "本品", "price_cny": 399, "specifications": {"续航": "30天"}},
        "market_config": {
            "scene_tags": ["情侣", "送礼"],
            "competitors": [
                {"id": 1, "brand": "飞科", "product_name": "FS891", "price_cny": 199},
                {"id": 2, "brand": "品牌B", "product_name": "竞品B", "price_cny": 299},
            ],
        },
        "market_assumptions": {"assumed_market_competitor_count": 20},
        "decision_weight_profile": {"template": "douyin"},
        "simulation_params": {"sample_size": 1000},
    }


def _decisions() -> list[dict]:
    return [
        {
            "agent_id": "a1",
            "decision": "buy",
            "purchase_intent_score": 0.8,
            "sample_weight": 0.6,
            "maut_scores": {"function_fit": 0.8, "price_acceptance": 0.7, "promotion_bonus": 0.9, "brand_loyalty": 0.5, "social_influence": 0.7},
        },
        {
            "agent_id": "a2",
            "decision": "consider",
            "purchase_intent_score": 0.55,
            "sample_weight": 0.4,
            "maut_scores": {"function_fit": 0.6, "price_acceptance": 0.5, "promotion_bonus": 0.8, "brand_loyalty": 0.4, "social_influence": 0.6},
        },
    ]


def test_market_share_has_dual_scope_and_monotonic_scenarios() -> None:
    chart = build_chart_data(
        _snapshot(),
        {"product_competition": []},
        [],
        _decisions(),
        {"purchase_intent_avg": 0.68},
        plan_type="pro",
    )
    scope = chart["market_share_scope"]
    scenarios = chart["market_share_scenarios"]
    assert scope["method"] == "closed_competitor_set"
    assert scope["configured_competitor_count"] == 2
    assert scope["assumed_market_competitor_count"] == 20
    assert scope["simulation_environment_share"] > scope["full_market_scenario_share"]
    assert len(scenarios) == 46
    assert all(left["share"] >= right["share"] for left, right in zip(scenarios, scenarios[1:]))
    assert scope["relative_competitiveness_index"] > 0


def test_explicit_competitor_set_is_not_expanded_by_rag_evidence() -> None:
    evidence = {
        "product_competition": [
            {
                "source_type": "product_competitor",
                "source": "RAG额外竞品",
                "score": 0.9,
                "raw": {"id": 99, "product_name": "未选择的证据产品", "price_cny": 199},
            }
        ]
    }
    competitors = collect_competitors(_snapshot(), evidence, "pro")
    assert [item["id"] for item in competitors] == [1, 2]


def test_channel_profile_changes_weights_and_precomputes_scenarios() -> None:
    profile = decision_weight_profile(_snapshot())
    summary = build_decision_model_summary(_decisions(), _snapshot())
    assert profile["template"] == "douyin"
    assert profile["weights"]["promotion_bonus"] == 0.2
    assert round(sum(profile["weights"].values()), 6) == 1.0
    assert {item["template"] for item in summary["channel_scenarios"]} == {"default", "douyin", "tmall", "offline_premium"}
    assert "0.20*B_pr" in summary["formula_resolved"]


def test_marketing_funnel_uses_external_traffic_and_scene_fission() -> None:
    funnel = build_propagation_funnel(_snapshot(), [], _decisions(), {"rounds_executed": 3})
    assert funnel["model"] == "marketing_compartment_v1"
    assert funnel["scene_fission_factor"] == 1.25
    assert len(funnel["rounds"]) == 3
    assert any(link["source"] == "外部流量" and link["target"] == "已曝光" for link in funnel["links"])
    assert all(round_row["states"]["已购买"] >= 0 for round_row in funnel["rounds"])
    assert round(sum(funnel["sentiment_evolution"][0][key] for key in ("positive", "neutral", "negative")), 1) == 100.0


def test_reviewed_price_bundle_is_complete_and_uses_stable_locations() -> None:
    actions = load_actions()
    assert len(actions) == 369
    assert sum(item.action == "update_price" for item in actions) == 366
    assert sum(item.action.startswith("delete") for item in actions) == 3
    flyco = next(item for item in actions if item.brand == "飞科" and item.confirmed_sku == "FS891")
    assert flyco.source_file == "output_morep2.jsonl"
    assert flyco.source_row == 18
    assert flyco.price_cny == 199


def test_custom_competitor_price_gap_is_explicitly_labeled() -> None:
    competitors = configured_competitors(
        {"competitors": [{"id": -1, "product_name": "手工新增型号", "brand": "", "is_custom": True, "source": "custom"}]}
    )
    gaps = price_data_gaps(competitors)
    assert gaps["missing_count"] == 1
    assert gaps["custom_competitor_gap_count"] == 1
    assert gaps["missing_items"][0]["is_custom"] is True
    assert gaps["missing_items"][0]["competitor_type"] == "custom"
    assert "自定义竞品" in gaps["missing_items"][0]["reason"]
    assert set(gaps["custom_competitor_gaps"][0]["missing_fields"]) == {"brand", "price_cny"}


def test_decision_thresholds_keep_absolute_meaning() -> None:
    assert adaptive_thresholds([0.1, 0.2, 0.3, 0.4]) == (0.45, 0.68)
    assert adaptive_thresholds([0.7, 0.8, 0.9, 0.95]) == (0.45, 0.68)


def test_brand_loyalty_does_not_depend_on_process_hash_or_agent_id() -> None:
    product = {"brand": "测试品牌"}
    common = {
        "preferred_brands": ["测试品牌"],
        "decision_style": "品牌信任型",
        "price_sensitivity": "medium",
    }
    first = brand_loyalty_score({**common, "agent_id": "agent_001"}, product)
    second = brand_loyalty_score({**common, "agent_id": "agent_999"}, product)
    assert first == second


def test_price_competitiveness_is_monotonic_without_early_floor() -> None:
    values = [price_competitiveness(price, 100) for price in (80, 100, 110, 120, 150)]
    assert values == sorted(values, reverse=True)
    assert values[2] > values[3] > values[4]
    assert price_competitiveness(100, 100) == 70


def test_funnel_prefers_weighted_round_distribution() -> None:
    social = {
        "rounds_executed": 1,
        "round_summaries": [
            {
                "decision_distribution": {"buy": 1, "not_buy": 1},
                "decision_weighted_distribution": {"buy": 0.9, "not_buy": 0.1},
            }
        ],
    }
    funnel = build_propagation_funnel(_snapshot(), [], _decisions(), social)
    sentiment = funnel["sentiment_evolution"][0]
    assert sentiment["positive"] == 90.0
    assert sentiment["negative"] == 10.0
