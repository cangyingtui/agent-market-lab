from __future__ import annotations

from collections import deque

import pytest

from app.export_service import sanitize_report
from engine.agent_generator import generate_agents
from engine.chart_data import social_evolution_rows
from engine.social_network import representative_agent_count
from engine.social_simulation import run_social_simulation


pytestmark = pytest.mark.no_db


def _snapshot(sample_size: int = 1000) -> dict:
    return {
        "product_definition": {
            "product_name": "测试智能产品",
            "brand": "测试品牌",
            "price_cny": 1999,
            "specifications": {"续航": "长", "可靠性": "高"},
        },
        "market_config": {
            "crowd_segments": [
                {"name": "年轻白领", "ratio": 60, "profile": {"price_sensitivity": "medium", "feature_priorities": ["续航"]}},
                {"name": "品质家庭", "ratio": 40, "profile": {"price_sensitivity": "low", "feature_priorities": ["可靠性"]}},
            ]
        },
        "simulation_params": {
            "sample_size": sample_size,
            "random_seed": 20260530,
            "social_network": {
                "enabled": True,
                "topology": "connected_watts_strogatz",
                "k": 4,
                "rewire_probability": 0.3,
                "max_rounds": 3,
                "convergence_threshold": 0.02,
                "trust_sensitivity_min": 0.5,
                "trust_sensitivity_max": 1.0,
            },
        },
    }


def _is_connected(agents: list[dict]) -> bool:
    if not agents:
        return True
    neighbors = {agent["agent_id"]: set(agent.get("neighbors") or []) for agent in agents}
    visited = {agents[0]["agent_id"]}
    queue = deque(visited)
    while queue:
        current = queue.popleft()
        for neighbor in neighbors[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited) == len(agents)


def test_representative_agent_count_is_bounded() -> None:
    assert representative_agent_count(1000) == 60
    assert representative_agent_count(5000) == 150
    assert representative_agent_count(10000) == 300
    assert representative_agent_count(999999) == 300


def test_social_network_is_deterministic_connected_and_weighted() -> None:
    first = generate_agents(_snapshot(), {})
    second = generate_agents(_snapshot(), {})

    assert len(first["agents"]) == 60
    assert first["social_network"]["node_count"] == 60
    assert 3.5 <= first["social_network"]["average_degree"] <= 4.5
    assert _is_connected(first["agents"])
    assert round(sum(agent["sample_weight"] for agent in first["agents"]), 6) == 1.0
    assert [agent["neighbors"] for agent in first["agents"]] == [agent["neighbors"] for agent in second["agents"]]
    assert [agent["trust_sensitivity"] for agent in first["agents"]] == [agent["trust_sensitivity"] for agent in second["agents"]]
    assert all(0.5 <= agent["trust_sensitivity"] <= 1.0 for agent in first["agents"])
    assert all(agent["persona"] for agent in first["agents"])
    assert all(agent["base_maut_scores"] for agent in first["agents"])


def test_social_propagation_updates_neighbor_influence_and_stops_by_round_limit() -> None:
    snapshot = _snapshot()
    agents = [
        {
            "agent_id": "agent_001",
            "segment": "高意愿",
            "segment_ratio": 50,
            "sample_weight": 0.5,
            "neighbors": ["agent_002"],
            "trust_sensitivity": 1.0,
            "base_maut_scores": {"function_fit": 0.95, "price_acceptance": 0.9, "promotion_bonus": 0.2, "brand_loyalty": 0.8},
        },
        {
            "agent_id": "agent_002",
            "segment": "低意愿",
            "segment_ratio": 50,
            "sample_weight": 0.5,
            "neighbors": ["agent_001"],
            "trust_sensitivity": 1.0,
            "base_maut_scores": {"function_fit": 0.2, "price_acceptance": 0.2, "promotion_bonus": 0.05, "brand_loyalty": 0.3},
        },
    ]
    initial = [
        {"agent_id": "agent_001", "purchase_intent_score": 0.8, "decision": "buy"},
        {"agent_id": "agent_002", "purchase_intent_score": 0.2, "decision": "not_buy"},
    ]

    result = run_social_simulation(snapshot, {}, agents, initial)

    assert 2 <= result["rounds_executed"] <= 3
    assert result["round_summaries"][1]["max_score_change"] > 0
    assert "decision_weighted_distribution" in result["round_summaries"][0]
    assert round(sum(result["round_summaries"][0]["decision_weighted_distribution"].values()), 6) == 1.0
    assert all(item["simulation_round"] == result["rounds_executed"] for item in result["final_decisions"])
    assert any("neighbor_purchase_intent_avg" in item for item in result["final_decisions"])


def test_social_chart_access_and_public_sanitization() -> None:
    aggregation = {
        "social_evolution": [
            {
                "round": 1,
                "overall_purchase_intent": 0.58,
                "social_influence_avg": 0.52,
                "max_score_change": 0,
                "segment_evolution": [{"name": "年轻白领", "value": 62, "ratio": 100, "count": 10}],
            }
        ]
    }
    assert [row["name"] for row in social_evolution_rows(aggregation, "basic")] == ["整体人群"]
    assert [row["name"] for row in social_evolution_rows(aggregation, "pro")] == ["整体人群", "年轻白领"]

    public = sanitize_report(
        {
            "agent_samples": [{"agent_id": "agent_001", "neighbors": ["agent_002"], "base_maut_scores": {"function_fit": 0.5}}],
            "purchase_decisions": [{"agent_id": "agent_001", "neighbor_purchase_intent_avg": 0.6, "social_score_change": 0.1}],
            "social_simulation": {"rounds_executed": 2, "node_count": 60},
        },
        public=True,
    )
    assert "neighbors" not in public["agent_samples"][0]
    assert "base_maut_scores" not in public["agent_samples"][0]
    assert "neighbor_purchase_intent_avg" not in public["purchase_decisions"][0]
    assert public["social_simulation"]["node_count"] == 60
