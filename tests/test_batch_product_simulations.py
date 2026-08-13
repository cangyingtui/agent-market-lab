from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from scripts.batch_product_simulations import (
    SHEETS,
    build_parser,
    canonical_category_subcategory,
    compile_cases,
    create_workbook,
    custom_competitor_ids,
    has_expected_batch_prefix,
    is_same_library_product,
    json_transport_value,
    project_name,
    validate_workbook,
)


pytestmark = pytest.mark.no_db


class FakeProductClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def select_library_competitors(
        self,
        target: dict[str, Any],
        count: int,
        *,
        exclude_products: list[dict[str, Any]] = [],
    ) -> list[dict[str, Any]]:
        self.calls.append({"count": count, "excluded": list(exclude_products)})
        return [
            {
                "id": 1000 + index,
                "product_name": f"产品库竞品{index}",
                "brand": "产品库品牌",
                "confirmed_sku": f"LIB-{index}",
                "price_cny": 300 + index,
            }
            for index in range(1, count + 1)
        ]


def _sample_context(tmp_path: Path, *, competitor_ids: str, target_count: int) -> dict[str, Any]:
    workbook = create_workbook(include_samples=True, sample_count=1)
    case_sheet = workbook[SHEETS["cases"]]
    case_sheet.cell(2, 5).value = ""  # competitor_mode is a legacy, optional column.
    case_sheet.cell(2, 6).value = competitor_ids
    case_sheet.cell(2, 7).value = target_count
    path = tmp_path / "input.xlsx"
    workbook.save(path)
    issues, context = validate_workbook(path)
    assert not [item for item in issues if item.severity == "error"]
    return context


def test_blank_competitors_are_selected_entirely_from_library(tmp_path: Path) -> None:
    context = _sample_context(tmp_path, competitor_ids="", target_count=5)
    client = FakeProductClient()

    compiled = compile_cases(context, client)

    competitors = compiled[0]["market_config"]["competitors"]
    assert len(competitors) == 5
    assert client.calls[0]["count"] == 5
    assert client.calls[0]["excluded"] == []


def test_custom_competitors_are_kept_and_library_fills_remaining_slots(tmp_path: Path) -> None:
    context = _sample_context(
        tmp_path,
        competitor_ids="DEMO-TB-B1|DEMO-TB-C1",
        target_count=5,
    )
    client = FakeProductClient()

    compiled = compile_cases(context, client)

    competitors = compiled[0]["market_config"]["competitors"]
    assert len(competitors) == 5
    assert [item["product_name"] for item in competitors[:2]] == ["智测声波牙刷B1", "智测声波牙刷C1"]
    assert all(item["is_custom"] is True for item in competitors[:2])
    assert client.calls[0]["count"] == 3
    assert len(client.calls[0]["excluded"]) == 2


def test_blank_crowd_segments_compile_to_single_full_ratio_segment(tmp_path: Path) -> None:
    workbook = create_workbook(include_samples=True, sample_count=1)
    profile_sheet = workbook[SHEETS["profiles"]]
    profile_sheet.cell(2, 4).value = ""
    path = tmp_path / "blank_segments.xlsx"
    workbook.save(path)
    issues, context = validate_workbook(path)
    assert not [item for item in issues if item.severity == "error"]

    compiled = compile_cases(context, FakeProductClient())

    market = compiled[0]["market_config"]
    assert market["crowd_segments"] == [
        {
            "name": market["target_crowd"],
            "ratio": 100,
            "is_custom": True,
            "profile": market["crowd_profile"],
        }
    ]


def test_product_row_url_and_price_type_are_valid_price_provenance(tmp_path: Path) -> None:
    workbook = create_workbook(include_samples=True, sample_count=1)
    evidence_sheet = workbook[SHEETS["evidence"]]
    rows_to_delete = []
    for row_number in range(2, evidence_sheet.max_row + 1):
        if (
            evidence_sheet.cell(row_number, 2).value == "DEMO-TB-A1"
            and evidence_sheet.cell(row_number, 3).value == "price_cny"
        ):
            rows_to_delete.append(row_number)
    for row_number in reversed(rows_to_delete):
        evidence_sheet.delete_rows(row_number)
    path = tmp_path / "product_row_price_source.xlsx"
    workbook.save(path)

    issues, context = validate_workbook(path)

    assert not [item for item in issues if item.error_code == "TARGET_PRICE_EVIDENCE_REQUIRED"]
    compiled = compile_cases(context, FakeProductClient())
    provenance = compiled[0]["product_definition"]["data_provenance"]
    assert provenance["price_type"] == "日常价"
    assert provenance["product_url"].startswith("https://")


def test_custom_competitors_can_be_inferred_from_target_family_ids() -> None:
    case = {"target_product_id": "MB-MON-001", "competitor_product_ids": ""}
    context = {
        "products": {
            "MB-MON-001": {"category": "母婴用品", "subcategory": "婴儿监视器"},
            "MB-MON-C01": {"category": "母婴用品", "subcategory": "婴儿监视器"},
            "MB-MON-C02": {"category": "母婴用品", "subcategory": "婴儿监视器"},
            "MB-WARM-C01": {"category": "母婴用品", "subcategory": "奶瓶消毒器/恒温壶"},
        }
    }

    assert custom_competitor_ids(case, context) == ["MB-MON-C01", "MB-MON-C02"]


def test_run_parser_accepts_case_id_allowlist() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run",
            "--input",
            "input.xlsx",
            "--batch-id",
            "batch_001",
            "--case-id",
            "case_a",
            "--case-id",
            "case_b",
        ]
    )

    assert args.case_ids == ["case_a", "case_b"]


@pytest.mark.parametrize(
    ("category", "subcategory", "expected"),
    [
        ("消费电子", "智能手表", ("消费电子", "智能手表/手环")),
        ("家用电器", "微波炉", ("家用电器", "微波炉/烤箱/蒸烤箱")),
        ("个护健康", "血糖仪", ("个护健康", "血压计/血糖仪")),
        ("母婴用品", "婴儿推车", ("母婴用品", "婴儿推车")),
    ],
)
def test_category_aliases_are_normalized(category, subcategory, expected) -> None:
    assert canonical_category_subcategory(category, subcategory) == expected


def test_showcase_project_name_is_prominent_and_keeps_batch_identity() -> None:
    name = project_name(
        "batch_001",
        {"case_id": "AMAZON-KINDLEPW-01", "project_name": "Kindle Paperwhite", "showcase": True},
    )
    assert name.startswith("【代表案例】[TEST-BATCH:batch_001:AMAZON-KINDLEPW-01]")
    assert has_expected_batch_prefix(name, "batch_001", "AMAZON-KINDLEPW-01") is True
    assert has_expected_batch_prefix(
        "[TEST-BATCH:batch_001:ordinary_001] 普通案例", "batch_001", "ordinary_001"
    ) is True
    assert has_expected_batch_prefix(name, "another_batch", "AMAZON-KINDLEPW-01") is False


def test_json_transport_value_normalizes_api_dates_and_decimals() -> None:
    normalized = json_transport_value(
        {"released_at": datetime(2026, 8, 9, 12, 30, 5), "price": Decimal("1199.50")}
    )
    assert normalized == {"released_at": "2026-08-09T12:30:05", "price": 1199.5}


@pytest.mark.parametrize(
    ("target", "candidate"),
    [
        (
            {"brand": "小米", "product_name": "Xiaomi 15 Ultra", "price_cny": 6499},
            {"brand": "Xiaomi", "product_name": "小米15 Ultra", "price_cny": 6499},
        ),
        (
            {"brand": "华为", "product_name": "HUAWEI MatePad Pro 13.2", "price_cny": 5199},
            {"brand": "Huawei", "product_name": "华为MatePad Pro 13.2英寸", "price_cny": 5199},
        ),
        (
            {"brand": "Sony", "product_name": "PlayStation 5 Slim", "price_cny": 3999},
            {"brand": "索尼", "product_name": "PlayStation 5 轻薄版", "price_cny": 3499},
        ),
    ],
)
def test_library_selection_detects_same_product_across_name_variants(target, candidate) -> None:
    assert is_same_library_product(target, candidate) is True


def test_library_selection_keeps_distinct_same_brand_models() -> None:
    target = {"brand": "Apple", "product_name": "iPhone 16 Pro", "price_cny": 7999}
    candidate = {"brand": "Apple", "product_name": "iPhone 16 Pro Max", "price_cny": 9999}
    assert is_same_library_product(target, candidate) is False
