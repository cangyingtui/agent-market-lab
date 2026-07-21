from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import or_, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ROOT_DIR  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Product  # noqa: E402
from app.time_utils import utc_now_naive  # noqa: E402
from knowledge_model.data_enrichment import build_product_enrichment_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成产品数据补全候选清单，不联网、不改正式产品表")
    parser.add_argument("--limit", type=int, default=100, help="最多输出多少条候选")
    parser.add_argument("--subcategory", default="", help="按子品类过滤")
    parser.add_argument("--output", default="", help="输出 JSONL 路径，默认 logs/data_enrichment_candidates/YYYYMMDD_HHMMSS.jsonl")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else ROOT_DIR / "logs" / "data_enrichment_candidates" / f"{utc_now_naive().strftime('%Y%m%d_%H%M%S')}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        stmt = select(Product).where(
            Product.is_active.is_(True),
            or_(
                Product.price_cny.is_(None),
                Product.product_name.is_(None),
                Product.specifications.is_(None),
            ),
        )
        if args.subcategory:
            stmt = stmt.where(Product.subcategory == args.subcategory)
        rows = list(db.scalars(stmt.order_by(Product.subcategory, Product.brand, Product.id).limit(args.limit)))

    with output_path.open("w", encoding="utf-8") as file:
        for product in rows:
            candidate = build_product_enrichment_candidate(product, "产品名称、价格或规格字段不完整")
            file.write(json.dumps(candidate, ensure_ascii=False, default=str) + "\n")

    print(json.dumps({"output": str(output_path), "count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
