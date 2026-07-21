from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Product  # noqa: E402


def pct(part: int, total: int) -> float:
    return round(part * 100 / total, 2) if total else 0.0


def main() -> int:
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(Product)) or 0
        named = db.scalar(select(func.count()).select_from(Product).where(Product.product_name.is_not(None))) or 0
        priced = db.scalar(select(func.count()).select_from(Product).where(Product.price_cny.is_not(None))) or 0
        active = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0
        with_specs = 0
        empty_specs = 0
        spec_key_counter: dict[str, int] = {}
        category_rows = db.execute(
            select(Product.subcategory, func.count())
            .group_by(Product.subcategory)
            .order_by(func.count().desc())
            .limit(15)
        ).all()
        for specs in db.scalars(select(Product.specifications)):
            if isinstance(specs, dict) and specs:
                with_specs += 1
                for key in specs.keys():
                    spec_key_counter[str(key)] = spec_key_counter.get(str(key), 0) + 1
            else:
                empty_specs += 1

    result = {
        "total_products": int(total),
        "active_products": int(active),
        "named_products": int(named),
        "priced_products": int(priced),
        "with_specifications": int(with_specs),
        "empty_specifications": int(empty_specs),
        "missing_rates": {
            "product_name_missing_pct": pct(total - named, total),
            "price_cny_missing_pct": pct(total - priced, total),
            "specifications_missing_pct": pct(empty_specs, total),
        },
        "top_subcategories": [
            {"subcategory": subcategory, "count": int(count)}
            for subcategory, count in category_rows
        ],
        "top_spec_keys": [
            {"key": key, "count": count}
            for key, count in sorted(spec_key_counter.items(), key=lambda item: item[1], reverse=True)[:20]
        ],
        "notes": [
            "FAISS metadata 当前主要是用户画像，竞品证据依赖 products 表。",
            "price_cny 缺失会让价格分析偏保守；报告会提示价格数据不完整。",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
