from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    MarketCrowdTemplate,
    MarketSceneTemplate,
    MarketStrategyTemplate,
    Product,
    ProductCategory,
    ProductFieldTemplate,
    SystemFeatureFlag,
    User,
)


def count_rows(db, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return int(db.scalar(stmt) or 0)


def main() -> int:
    checks: list[dict[str, object]] = []

    def add_check(name: str, value: object, ok: bool, expected: str) -> None:
        checks.append({"name": name, "value": value, "ok": ok, "expected": expected})

    with SessionLocal() as db:
        categories = count_rows(db, ProductCategory)
        fields = count_rows(db, ProductFieldTemplate)
        products = count_rows(db, Product)
        active_products = count_rows(db, Product, Product.is_active.is_(True))
        categorized_products = count_rows(
            db,
            Product,
            Product.is_active.is_(True),
            Product.category_id.is_not(None),
        )
        crowd_templates = count_rows(db, MarketCrowdTemplate)
        strategy_templates = count_rows(db, MarketStrategyTemplate)
        scene_templates = count_rows(db, MarketSceneTemplate)
        feature_flags = count_rows(db, SystemFeatureFlag)

        demo_users = {
            user.username: user.plan_type
            for user in db.scalars(
                select(User).where(User.username.in_(["pro@example", "normal@example"]))
            )
        }

    add_check("database_url", engine.url.render_as_string(hide_password=True), True, "应指向当前项目 MySQL")
    add_check("product_categories", categories, categories > 0, "大于 0，正常约 64")
    add_check("product_field_templates", fields, fields > 0, "大于 0，正常约 425")
    add_check("products", products, products > 0, "大于 0，正常约 947")
    add_check("active_products", active_products, active_products > 0, "大于 0")
    add_check(
        "categorized_active_products",
        categorized_products,
        categorized_products > 0,
        "大于 0；若为 0，通常是先 seed_products 后 seed_categories 导致产品无分类",
    )
    add_check("market_crowd_templates", crowd_templates, crowd_templates > 0, "大于 0，正常约 15")
    add_check("market_strategy_templates", strategy_templates, strategy_templates > 0, "大于 0，正常约 3")
    add_check("market_scene_templates", scene_templates, scene_templates > 0, "大于 0，正常约 4")
    add_check("system_feature_flags", feature_flags, feature_flags > 0, "大于 0，正常约 5")
    add_check("pro@example", demo_users.get("pro@example"), demo_users.get("pro@example") == "pro", "存在且 plan_type=pro")
    add_check(
        "normal@example",
        demo_users.get("normal@example"),
        demo_users.get("normal@example") == "basic",
        "存在且 plan_type=basic",
    )

    ok = all(bool(item["ok"]) for item in checks)
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
    if not ok:
        print(
            "\n数据未就绪：请按顺序执行 init_db、migrate_v24_indexes、seed_categories、"
            "seed_products、seed_market_templates、seed_feature_flags、seed_demo_users。",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
