from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Product  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出数据库中缺少价格的竞品/产品清单，用于本地百炼补价。")
    parser.add_argument("--output", default="missing_product_prices.csv", help="导出的 CSV 文件路径。")
    parser.add_argument("--limit", type=int, default=1000, help="最多导出多少条。")
    parser.add_argument("--offset", type=int, default=0, help="从缺价列表的偏移位置开始导出。")
    parser.add_argument("--category", default="", help="按大品类精确筛选，可选。")
    parser.add_argument("--subcategory", default="", help="按小品类精确筛选，可选。")
    parser.add_argument("--search", default="", help="按品牌/产品名/SKU 模糊筛选，可选。")
    parser.add_argument("--include-inactive", action="store_true", help="包含非 active 产品。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = [
        Product.price_cny.is_(None),
        Product.product_name.is_not(None),
    ]
    if not args.include_inactive:
        filters.append(Product.is_active.is_(True))
    if args.category:
        filters.append(Product.category == args.category)
    if args.subcategory:
        filters.append(Product.subcategory == args.subcategory)
    if args.search:
        pattern = f"%{args.search}%"
        filters.append(
            (Product.product_name.like(pattern))
            | (Product.brand.like(pattern))
            | (Product.confirmed_sku.like(pattern))
        )

    stmt = (
        select(Product)
        .where(*filters)
        .order_by(Product.category, Product.subcategory, Product.brand, Product.id)
        .offset(max(args.offset, 0))
        .limit(max(args.limit, 1))
    )

    rows = []
    with SessionLocal() as db:
        for item in db.scalars(stmt):
            rows.append(
                {
                    "id": item.id,
                    "category_id": item.category_id or "",
                    "category": item.category or "",
                    "subcategory": item.subcategory or "",
                    "brand": item.brand or "",
                    "product_name": item.product_name or "",
                    "confirmed_sku": item.confirmed_sku or "",
                    "specifications_json": json.dumps(item.specifications or {}, ensure_ascii=False, default=str),
                    "source_file": item.source_file or "",
                    "source_row": item.source_row or "",
                }
            )

    fieldnames = [
        "id",
        "category_id",
        "category",
        "subcategory",
        "brand",
        "product_name",
        "confirmed_sku",
        "specifications_json",
        "source_file",
        "source_row",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已导出 {len(rows)} 条缺价产品：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
