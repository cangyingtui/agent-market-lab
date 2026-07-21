from __future__ import annotations

import shutil
from pathlib import Path

from engine.agent_generator import generate_agents
from engine.aggregation import aggregate_results
from engine.decision_model import generate_purchase_decisions
from engine.formal_logger import write_formal_task_log
from engine.maut_model import MAUT_WEIGHTS, build_decision_model_summary


def sample_snapshot() -> dict:
    return {
        "project_name": "pytest 正式仿真",
        "product_definition": {
            "product_name": "高端智能手机",
            "category": "消费电子",
            "subcategory": "智能手机",
            "price_cny": 4999,
            "specifications": {"电池": "5000mAh", "屏幕": "OLED 120Hz"},
        },
        "market_config": {
            "target_crowd": "高端用户",
            "strategy": "差异化",
            "crowd_profile": {
                "age_range": "28-45",
                "city_tier": "一线/新一线",
                "income_level": "高收入",
                "price_sensitivity": "low",
                "feature_priorities": ["续航", "屏幕"],
                "channel_preferences": ["品牌旗舰店"],
                "purchase_motivations": ["体验升级"],
                "risk_concerns": ["价格波动"],
            },
        },
    }


def sample_evidence() -> dict:
    return {
        "product_competition": [
            {
                "source": "product:7",
                "source_type": "product_competitor",
                "score": 5.6,
                "snippet": "Xiaomi Redmi K80，价格未确认。battery=5500mAh；display=OLED直屏",
                "raw": {"price_missing": True},
            }
        ],
        "crowd_preference": [
            {
                "source": "用户画像数据_pytest",
                "source_type": "user_profile",
                "score": 0.7,
                "snippet": "用户价格敏感度高，关注关键词：性价比;防水;续航",
            }
        ],
        "market_strategy": [],
    }


def test_agent_generation_has_required_fields() -> None:
    result = generate_agents(sample_snapshot(), sample_evidence(), count=4)
    assert result["prompt_version"].startswith("agent_generator")
    assert len(result["agents"]) == 4
    assert any(set(agent["preferred_features"]) & {"续航", "屏幕"} for agent in result["agents"])
    for agent in result["agents"]:
        assert agent["agent_id"].startswith("agent_")
        assert agent["segment"] == "高端用户"
        assert agent["price_sensitivity"] == "low"
        assert agent["city_tier"] == "一线/新一线"
        assert agent["channel_preferences"] == ["品牌旗舰店"]


def test_purchase_decision_fallback_when_llm_key_missing(monkeypatch) -> None:
    monkeypatch.setattr("engine.decision_model.settings.llm_api_key", "")
    agents = generate_agents(sample_snapshot(), sample_evidence(), count=3)["agents"]
    result = generate_purchase_decisions(sample_snapshot(), sample_evidence(), agents)
    assert result["is_fallback"] is True
    assert len(result["decisions"]) == 3
    assert all(0 <= item["purchase_intent_score"] <= 1 for item in result["decisions"])
    assert round(sum(MAUT_WEIGHTS.values()), 2) == 1.0
    assert all("maut_scores" in item for item in result["decisions"])
    assert all(item["confidence"]["level"] in {"high", "medium", "low"} for item in result["decisions"])
    assert "decision_model" in result


def test_aggregation_outputs_metrics() -> None:
    agents = generate_agents(sample_snapshot(), sample_evidence(), count=3)["agents"]
    decisions = [
        {"agent_id": agents[0]["agent_id"], "purchase_intent_score": 0.8, "decision": "buy", "drivers": ["续航"], "blockers": []},
        {"agent_id": agents[1]["agent_id"], "purchase_intent_score": 0.5, "decision": "consider", "drivers": ["屏幕"], "blockers": ["价格"]},
        {"agent_id": agents[2]["agent_id"], "purchase_intent_score": 0.3, "decision": "not_buy", "drivers": [], "blockers": ["价格"]},
    ]
    result = aggregate_results(agents, decisions, sample_evidence(), sample_snapshot())
    assert result["purchase_intent_avg"] == 0.5333
    assert result["purchase_intent_distribution"]["buy"] == 1
    assert result["top_purchase_blockers"][0]["item"] == "价格"
    assert result["confidence"]["display_name"] == "证据置信度"
    assert set(result["confidence"]["components"]) == {
        "logic_format_score",
        "competitor_price_coverage_score",
        "rag_evidence_score",
        "crowd_profile_completeness_score",
    }
    assert all(0 <= item["score"] <= 1 for item in result["confidence"]["components"].values())


def test_evidence_confidence_drops_when_inputs_are_sparse() -> None:
    agents = [{"agent_id": "agent_001", "segment": "目标用户", "price_sensitivity": "medium", "preferred_features": []}]
    decisions = [{"agent_id": "agent_001", "purchase_intent_score": 0.5, "decision": "consider"}]
    result = aggregate_results(agents, decisions, {}, {"market_config": {}})
    confidence = result["confidence"]
    assert confidence["score"] < 1
    assert confidence["components"]["competitor_price_coverage_score"]["score"] == 0
    assert confidence["components"]["rag_evidence_score"]["score"] == 0
    assert confidence["components"]["crowd_profile_completeness_score"]["score"] < 0.7


def test_decision_model_summary_has_maut_formula(monkeypatch) -> None:
    monkeypatch.setattr("engine.decision_model.settings.llm_api_key", "")
    agents = generate_agents(sample_snapshot(), sample_evidence(), count=2)["agents"]
    result = generate_purchase_decisions(sample_snapshot(), sample_evidence(), agents)
    summary = build_decision_model_summary(result["decisions"])
    assert summary["formula"].startswith("PurchaseIntent")
    assert len(summary["weights"]) == 5
    assert "price_acceptance" in summary["dimension_scores"]
    assert summary["confidence"]["level"] in {"high", "medium", "low"}


def test_formal_logger_writes_json_and_summary() -> None:
    run_dir = Path("logs/test_runs/formal_logger_pytest")
    if run_dir.exists():
        shutil.rmtree(run_dir)
    path = write_formal_task_log(
        scenario_name="pytest 场景",
        task_id="sim_pytest",
        payload={"status": "completed", "report": {"is_fallback": False, "metrics": {"agent_count": 3}}},
        run_dir=run_dir,
    )
    assert Path(path).exists()
    assert (run_dir / "summary.jsonl").exists()
    assert "sim_pytest" in Path(path).read_text(encoding="utf-8")
    shutil.rmtree(run_dir)
