from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, select, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, engine  # noqa: E402
from app.models import ProductCategory, ProductFieldTemplate  # noqa: E402
from scripts.product_ui_schema_loader import schema_for_field  # noqa: E402


def ensure_ui_schema_column() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("product_field_templates")}
    if "ui_schema" in columns:
        print("skip product_field_templates.ui_schema")
        return
    dialect = engine.dialect.name
    if dialect == "mysql":
        ddl = "ALTER TABLE product_field_templates ADD COLUMN ui_schema JSON NULL AFTER ui_control"
    else:
        ddl = "ALTER TABLE product_field_templates ADD COLUMN ui_schema JSON"
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print("created product_field_templates.ui_schema")


def backfill_ui_schema() -> int:
    updated = 0
    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(ProductFieldTemplate, ProductCategory)
                .join(ProductCategory, ProductFieldTemplate.category_id == ProductCategory.id)
                .order_by(ProductCategory.sort_order, ProductFieldTemplate.sort_order)
            )
        )
        for field, category in rows:
            schema = schema_for_field(category.category, category.subcategory, field.field_name)
            if not schema:
                continue
            changed = False
            if field.ui_schema != schema:
                field.ui_schema = schema
                changed = True
            schema_unit = schema.get("unit")
            if schema_unit and field.unit != schema_unit:
                field.unit = str(schema_unit)
                changed = True
            schema_control = schema.get("controlType")
            if schema_control and field.ui_control != schema_control:
                field.ui_control = str(schema_control)
                changed = True
            default_weight = schema.get("defaultWeight")
            if isinstance(default_weight, (int, float)) and field.default_weight != float(default_weight):
                field.default_weight = float(default_weight)
                changed = True
            if changed:
                updated += 1
        db.commit()
    return updated


def main() -> int:
    ensure_ui_schema_column()
    updated = backfill_ui_schema()
    print(f"backfilled product_field_templates ui_schema rows={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
