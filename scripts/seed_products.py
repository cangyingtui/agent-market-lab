from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Product, ProductCategory  # noqa: E402


PRODUCT_FILES = (
    "output_part1.jsonl",
    "output_morep1.jsonl",
    "output_morep2.jsonl",
    "output_morep3.jsonl",
    "output_morep4.jsonl",
)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def quality_status(item: dict[str, Any]) -> str:
    if not any(item.get(key) for key in ("brand", "product_name", "confirmed_sku")):
        return "invalid"
    if not item.get("product_name") or item.get("price_cny") is None:
        return "partial"
    return "complete"


def best_category(spec_keys: set[str], categories: list[ProductCategory]) -> ProductCategory | None:
    best: tuple[int, int, str, ProductCategory] | None = None
    for category in categories:
        fields = getattr(category, "_seed_fields", set())
        overlap = spec_keys & fields
        if not overlap:
            continue
        score = len(overlap)
        coverage = int(100 * score / max(1, len(spec_keys)))
        candidate = (score, coverage, category.subcategory, category)
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    return best[3] if best else None


def load_category_field_map() -> dict[tuple[str, str], set[str]]:
    data = json.loads((PROJECT_ROOT / "data_seed" / "merged_categories.json").read_text(encoding="utf-8"))
    result = {}
    for item in data.get("categories", []):
        key = (item.get("category") or "", item.get("subcategory") or "")
        result[key] = {field.get("name") for field in item.get("fields", []) if field.get("name")}
    return result


def main() -> int:
    field_map = load_category_field_map()
    created = 0
    skipped = 0

    with SessionLocal() as db:
        categories = list(db.scalars(select(ProductCategory)))
        for category in categories:
            category._seed_fields = field_map.get((category.category, category.subcategory), set())

        for file_name in PRODUCT_FILES:
            path = PROJECT_ROOT / "data_seed" / file_name
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as file:
                for row_number, line in enumerate(file, 1):
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get("_migration_deleted"):
                        skipped += 1
                        continue
                    exists = db.scalar(
                        select(Product).where(
                            Product.source_file == file_name,
                            Product.source_row == row_number,
                        )
                    )
                    if exists:
                        skipped += 1
                        continue

                    specs = item.get("specifications") or {}
                    if not isinstance(specs, dict):
                        specs = {}
                    if isinstance(item.get("_price_enrichment"), dict):
                        specs = {**specs, "_price_enrichment": item["_price_enrichment"]}
                    category = best_category(set(specs.keys()), categories)
                    price = item.get("price_cny")
                    db.add(
                        Product(
                            category_id=category.id if category else None,
                            category=category.category if category else None,
                            subcategory=category.subcategory if category else None,
                            product_name=item.get("product_name"),
                            brand=item.get("brand"),
                            confirmed_sku=item.get("confirmed_sku"),
                            price_cny=float(price) if isinstance(price, (int, float)) else None,
                            specifications=specs,
                            source_file=file_name,
                            source_row=row_number,
                            collection_time=parse_datetime(item.get("_collection_time")),
                            quality_status=quality_status(item),
                            is_active=quality_status(item) == "complete",
                        )
                    )
                    created += 1
        db.commit()

    print(f"Seeded products: created={created}, skipped_existing={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
