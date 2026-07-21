from __future__ import annotations

from app.models import Product
from app.config import settings
from engine import data_enrichment
from engine.data_enrichment import auto_fill_missing_evidence_prices, candidate_to_evidence, regex_extract_candidate, run_data_enrichment
from knowledge_model.data_enrichment import build_product_enrichment_candidate


def test_build_product_enrichment_candidate_is_non_mutating() -> None:
    product = Product(
        id=123,
        brand="测试品牌",
        category="消费电子",
        subcategory="智能手机",
        product_name=None,
        confirmed_sku="测试 SKU",
        price_cny=None,
        specifications={},
    )

    candidate = build_product_enrichment_candidate(product, "pytest")

    assert candidate["product_id"] == 123
    assert candidate["status"] == "pending"
    assert "price_cny" in candidate["missing_fields"]
    assert "测试品牌" in candidate["suggested_search_query"]
    assert "不自动覆盖正式 products 表" in candidate["source_policy"]


def test_runtime_data_enrichment_is_disabled_without_switch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_data_enrichment", False)
    result = run_data_enrichment({}, {"product_competition": []})

    assert result["enabled"] is False
    assert result["status"] == "skipped"
    assert result["candidates"] == []


def test_web_candidate_to_evidence_marks_manual_review() -> None:
    candidate = {
        "product_id": 456,
        "brand": "候选品牌",
        "product_name": "候选竞品",
        "price_cny": 1999,
        "specifications": {"屏幕": "网页候选"},
        "source_urls": ["https://example.com/product"],
        "confidence": 0.62,
        "status": "candidate_pending_review",
    }

    evidence = candidate_to_evidence(candidate, rank=1)

    assert evidence["source_type"] == "product_competitor"
    assert evidence["raw"]["needs_human_review"] is True
    assert evidence["raw"]["source_urls"] == ["https://example.com/product"]
    assert "待人工确认" in evidence["snippet"]


def test_regex_extract_candidate_keeps_source_urls_and_price() -> None:
    candidate = regex_extract_candidate(
        {"id": 789, "product_name": "测试竞品", "brand": "测试品牌", "quality_reasons": ["missing_price"]},
        "测试竞品 价格 规格",
        [
            {
                "title": "测试竞品官网",
                "url": "https://example.com/spec",
                "content": "测试竞品参考价格 ¥2999 元，支持防水和续航优化。",
            }
        ],
    )

    assert candidate["price_cny"] == 2999
    assert candidate["source_urls"] == ["https://example.com/spec"]
    assert candidate["specifications"]["防水"] == "网页候选中出现，待人工确认"
    assert candidate["status"] == "candidate_pending_review"


def test_runtime_data_enrichment_enabled_generates_candidates_without_writing_products(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_data_enrichment", True)
    monkeypatch.setattr(settings, "enrichment_provider", "tavily")
    monkeypatch.setattr(settings, "enrichment_api_key", "pytest-key")
    monkeypatch.setattr(settings, "enrichment_max_items_per_run", 2)
    monkeypatch.setattr(
        data_enrichment,
        "tavily_search",
        lambda query: [
            {
                "title": "候选竞品参数",
                "url": "https://example.com/candidate",
                "content": "候选竞品售价 3299 元，屏幕和电池参数待确认。",
            }
        ],
    )
    monkeypatch.setattr(data_enrichment, "llm_extract_candidate", lambda item, query, results: None)

    result = run_data_enrichment(
        {
            "product_definition": {"category": "消费电子", "subcategory": "智能手机"},
            "market_config": {
                "competitors": [
                    {"id": 1, "brand": "候选品牌", "product_name": "候选竞品", "price_cny": None, "specifications": {}}
                ]
            },
        },
        {"product_competition": []},
    )

    assert result["enabled"] is True
    assert result["status"] == "completed"
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["price_cny"] == 3299
    assert candidate["source_urls"] == ["https://example.com/candidate"]
    assert candidate["status"] == "candidate_pending_review"


def test_auto_fill_missing_evidence_prices_updates_runtime_evidence_only() -> None:
    evidence = {
        "competitor_query": [
            {
                "source": "product:1",
                "source_type": "product_competitor",
                "matched_fields": ["quality.price_missing"],
                "snippet": "候选品牌 候选竞品，价格未确认。屏幕=OLED",
                "raw": {
                    "id": 1,
                    "brand": "候选品牌",
                    "product_name": "候选竞品",
                    "price_cny": None,
                    "price_missing": True,
                    "needs_enrichment": True,
                    "quality": {"has_name": True, "has_specs": True, "has_price": False, "needs_enrichment": True},
                },
            }
        ]
    }
    updates = auto_fill_missing_evidence_prices(
        evidence,
        [
            {
                "product_id": 1,
                "brand": "候选品牌",
                "product_name": "候选竞品",
                "price_cny": 3299,
                "source_urls": ["https://example.com/candidate"],
            }
        ],
    )

    item = evidence["competitor_query"][0]
    assert updates == [
        {
            "evidence_group": "competitor_query",
            "source": "product:1",
            "product_id": "1",
            "price_cny": 3299.0,
            "source_urls": ["https://example.com/candidate"],
        }
    ]
    assert item["raw"]["price_cny"] == 3299.0
    assert item["raw"]["price_missing"] is False
    assert item["raw"]["enrichment_status"] == "auto_filled_web_price"
    assert item["raw"]["quality"]["has_price"] is True
    assert item["raw"]["needs_enrichment"] is False
    assert "价格约3299元" in item["snippet"]
    assert "web_enrichment_price" in item["matched_fields"]
