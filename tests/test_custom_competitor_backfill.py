from __future__ import annotations

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.custom_competitor_backfill import (
    custom_competitors_from_snapshot,
    required_fields_missing,
    similarity_result,
)
from app.models import CustomCompetitorBackfillJob, Product
from engine.monitor import custom_competitor_backfill_is_idle


pytestmark = pytest.mark.no_db


def test_backfill_job_table_compiles_for_mysql():
    ddl = str(CreateTable(CustomCompetitorBackfillJob.__table__).compile(dialect=mysql.dialect()))
    assert "custom_competitor_backfill_jobs" in ddl
    assert "uq_custom_competitor_backfill_project_snapshot" in ddl


def product(*, category: str = "个护健康", subcategory: str = "电动牙刷", brand: str = "萤石", price: float = 420) -> Product:
    return Product(
        id=1,
        category=category,
        subcategory=subcategory,
        product_name="库内产品",
        brand=brand,
        price_cny=price,
        specifications={},
        source_file="fixture",
        source_row=1,
        quality_status="complete",
        is_active=True,
    )


def custom(**overrides):
    value = {
        "product_name": "自定义竞品",
        "brand": "萤石 EZVIZ",
        "category": "个护健康",
        "subcategory": "电动牙刷",
        "price_cny": 399,
        "is_custom": True,
    }
    value.update(overrides)
    return value


def test_similarity_requires_category_brand_and_price_together():
    result = similarity_result(custom(), product())
    assert result["highly_similar"] is True
    assert result["category_match"] is True
    assert result["brand_similarity"] >= 0.85


def test_similarity_rejects_different_category_or_far_price():
    assert similarity_result(custom(), product(category="母婴用品"))["highly_similar"] is False
    assert similarity_result(custom(price_cny=999), product(price=420))["highly_similar"] is False


def test_extracts_only_custom_competitors():
    snapshot = {
        "market_config": {
            "competitors": [custom(), {"id": 12, "product_name": "库内竞品"}],
        }
    }
    assert custom_competitors_from_snapshot(snapshot) == [custom()]


def test_missing_required_fields_are_explicit():
    item = custom(product_name="", brand="", price_cny=None)
    assert required_fields_missing(item) == ["brand", "product_name", "price_cny"]


class FakeRedis:
    def __init__(self, *, queue_length: int = 0, heavy_lock: bool = False, running: bool = False):
        self.queue_length = queue_length
        self.heavy_lock = heavy_lock
        self.running = running

    def llen(self, _key):
        return self.queue_length

    def exists(self, _key):
        return int(self.heavy_lock)

    def scan_iter(self, _pattern, count=1):
        del count
        return iter(["simulation:project:1:running"] if self.running else [])


@pytest.mark.parametrize(
    ("redis", "expected"),
    [
        (FakeRedis(), True),
        (FakeRedis(queue_length=1), False),
        (FakeRedis(heavy_lock=True), False),
        (FakeRedis(running=True), False),
    ],
)
def test_backfill_only_runs_when_system_is_idle(redis, expected):
    assert custom_competitor_backfill_is_idle(redis) is expected
