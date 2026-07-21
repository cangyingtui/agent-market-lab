from __future__ import annotations

from app.database import SessionLocal
from engine.report_generator import build_fallback_report, classify_user_profile_text, generate_simulation_report
from knowledge_model.product_evidence import search_product_evidence


def test_product_evidence_matches_smartphone_specs() -> None:
    product_definition = {
        "product_name": "高端智能手机",
        "category": "消费电子",
        "subcategory": "智能手机",
        "price_cny": 4999,
        "specifications": {"电池": "5000mAh", "防水": "IP68"},
    }
    with SessionLocal() as db:
        items = search_product_evidence(db, product_definition, "高端智能手机 电池 价格", top_k=5)

    assert items
    assert items[0]["source_type"] == "product_competitor"
    assert "quality" in items[0]["raw"]
    assert items[0]["raw"]["quality"]["has_name"] is True
    assert any("specifications." in field for item in items for field in item["matched_fields"])


def test_product_evidence_matches_toothbrush_query() -> None:
    with SessionLocal() as db:
        items = search_product_evidence(db, {}, "电动牙刷 续航 防水", top_k=5)

    assert items
    assert all(item["type"] == "structured_product" for item in items)


def test_fallback_report_has_required_sections() -> None:
    snapshot = {
        "project_name": "测试项目",
        "product_definition": {"product_name": "测试智能手机", "subcategory": "智能手机", "price_cny": 3999},
        "market_config": {"target_crowd": "高端用户"},
    }
    evidence = {
        "product_competition": [
            {"source": "product:1", "source_type": "product_competitor", "score": 1.0, "snippet": "竞品证据"}
        ],
        "crowd_preference": [
            {"source": "用户画像数据_1", "source_type": "user_profile", "score": 0.9, "snippet": "用户证据"}
        ],
    }

    report = build_fallback_report(snapshot, evidence, error="测试 fallback")

    for key in (
        "executive_summary",
        "target_segments",
        "competitor_insights",
        "pricing_analysis",
        "strategy_recommendations",
        "risk_warnings",
        "evidence_used",
    ):
        assert key in report
    assert report["is_fallback"] is True
    assert report["pricing_analysis"]["competitor_price_coverage"]["price_coverage_pct"] == 0.0
    assert report["quality_warnings"]


def test_user_profile_evidence_classification() -> None:
    tags = classify_user_profile_text("用户价格敏感度高，关注关键词：防水;续航;性价比")
    assert "price_sensitivity" in tags
    assert "feature_preference" in tags


def test_generate_report_fallback_when_llm_key_missing(monkeypatch) -> None:
    monkeypatch.setattr("engine.report_generator.settings.llm_api_key", "")
    snapshot = {
        "project_name": "测试项目",
        "product_definition": {"product_name": "测试智能手机", "subcategory": "智能手机", "price_cny": 3999},
        "market_config": {"target_crowd": "高端用户"},
    }
    evidence = {
        "product_competition": [
            {
                "source": "product:1",
                "source_type": "product_competitor",
                "score": 1.0,
                "snippet": "竞品证据",
                "raw": {"price_missing": True},
            }
        ]
    }

    report = generate_simulation_report(snapshot, evidence)

    assert report["is_fallback"] is True
    assert report["fallback_reason"] == "LLM_API_KEY 未配置"
    assert report["llm_error"] == "LLM_API_KEY 未配置"
    assert report["evidence_used"]
