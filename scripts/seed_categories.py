from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import inspect, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, engine  # noqa: E402
from app.models import ProductCategory, ProductFieldTemplate  # noqa: E402
from scripts.product_ui_schema_loader import schema_for_field  # noqa: E402


DATA_PATH = PROJECT_ROOT / "data_seed" / "merged_categories.json"


def product_field_ui_schema_column_exists() -> bool:
    columns = {column["name"] for column in inspect(engine).get_columns("product_field_templates")}
    return "ui_schema" in columns


def main() -> int:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    categories = data.get("categories", [])
    created_categories = 0
    created_fields = 0
    has_ui_schema_column = product_field_ui_schema_column_exists()

    with SessionLocal() as db:
        for sort_order, item in enumerate(categories, 1):
            category_name = item.get("category") or ""
            subcategory = item.get("subcategory") or ""
            if not category_name or not subcategory:
                continue

            category = db.scalar(
                select(ProductCategory).where(
                    ProductCategory.category == category_name,
                    ProductCategory.subcategory == subcategory,
                )
            )
            if category is None:
                category = ProductCategory(
                    category=category_name,
                    subcategory=subcategory,
                    display_name=item.get("display_name") or subcategory,
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(category)
                db.flush()
                created_categories += 1

            existing_fields = {
                row.field_name: row
                for row in db.scalars(
                    select(ProductFieldTemplate).where(ProductFieldTemplate.category_id == category.id)
                )
            }
            for field_order, field in enumerate(item.get("fields", []), 1):
                field_name = field.get("name")
                if not field_name:
                    continue
                ui_schema = field.get("ui_schema") or schema_for_field(category_name, subcategory, field_name)
                default_weight = float((ui_schema or {}).get("defaultWeight") or field.get("default_weight") or 1.0)
                unit = field.get("unit") or (ui_schema or {}).get("unit")
                ui_control = field.get("ui_control") or (ui_schema or {}).get("controlType")
                existing = existing_fields.get(field_name)
                if existing is not None:
                    changed = False
                    updates = {
                        "field_type": field.get("type") or existing.field_type or "string",
                        "field_desc": field.get("desc") or existing.field_desc,
                        "unit": unit or existing.unit,
                        "ui_control": ui_control or existing.ui_control,
                        "default_weight": default_weight,
                        "is_required": bool(field.get("is_required") or existing.is_required or False),
                        "sort_order": field_order,
                    }
                    if has_ui_schema_column:
                        updates["ui_schema"] = ui_schema or existing.ui_schema
                    for attr, value in updates.items():
                        if getattr(existing, attr) != value:
                            setattr(existing, attr, value)
                            changed = True
                    if changed:
                        created_fields += 1
                    continue
                payload = {
                    "category_id": category.id,
                    "field_name": field_name,
                    "field_type": field.get("type") or "string",
                    "field_desc": field.get("desc"),
                    "unit": unit,
                    "ui_control": ui_control,
                    "default_weight": default_weight,
                    "is_required": bool(field.get("is_required") or False),
                    "sort_order": field_order,
                }
                if has_ui_schema_column:
                    payload["ui_schema"] = ui_schema
                db.add(ProductFieldTemplate(**payload))
                created_fields += 1
        db.commit()

    print(f"Seeded categories: created_categories={created_categories}, created_fields={created_fields}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
