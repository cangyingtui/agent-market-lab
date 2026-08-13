from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Product  # noqa: E402
from app.price_enrichment import estimate_product_price  # noqa: E402
from app.time_utils import utc_now_iso  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用百炼 OpenAI 兼容接口批量补齐产品缺失价格。")
    parser.add_argument("--limit", type=int, default=50, help="本次最多处理多少条缺价产品。")
    parser.add_argument("--offset", type=int, default=0, help="从缺价列表的偏移位置开始处理。")
    parser.add_argument("--dry-run", action="store_true", help="只打印估算结果，不写入数据库。")
    parser.add_argument("--min-confidence", type=float, default=None, help="覆盖配置中的最低置信度。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not settings.price_enrichment_enabled:
        print("PRICE_ENRICHMENT_ENABLED=false，已跳过。")
        return 0
    min_confidence = (
        float(args.min_confidence)
        if args.min_confidence is not None
        else settings.price_enrichment_min_confidence
    )
    scanned = 0
    updated = 0
    skipped = 0

    with SessionLocal() as db:
        products = list(
            db.scalars(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.price_cny.is_(None),
                    Product.product_name.is_not(None),
                )
                .order_by(Product.id)
                .offset(max(args.offset, 0))
                .limit(max(args.limit, 1))
            )
        )
        for product in products:
            scanned += 1
            estimate = estimate_product_price(product)
            if not estimate:
                skipped += 1
                print(f"[skip] #{product.id} {product.product_name}: 未获得可用价格")
                continue
            confidence = float(estimate.get("confidence") or 0)
            price = float(estimate.get("price_cny") or 0)
            if confidence < min_confidence or price <= 0:
                skipped += 1
                print(f"[low] #{product.id} {product.product_name}: {price} confidence={confidence:.2f}")
                continue
            print(f"[ok] #{product.id} {product.product_name}: {price} confidence={confidence:.2f}")
            if args.dry_run:
                continue
            product.price_cny = price
            specs = dict(product.specifications or {})
            specs["_price_enrichment"] = {
                **estimate,
                "provider": "bailian_openai_compatible",
                "updated_at": utc_now_iso(),
                "requires_manual_review": True,
            }
            product.specifications = specs
            updated += 1
        if updated and not args.dry_run:
            db.commit()

    print(f"完成：扫描 {scanned} 条，写入 {updated} 条，跳过 {skipped} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
