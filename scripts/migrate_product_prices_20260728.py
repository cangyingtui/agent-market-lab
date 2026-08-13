from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, update


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Product  # noqa: E402
from app.time_utils import utc_now_iso  # noqa: E402


MIGRATION_VERSION = "product_prices_20260728_v1"
BUNDLE_DIR = ROOT / "releases" / "price_enrichment"
MISSING_FILE = BUNDLE_DIR / "missing_product_prices.tsv"
REVIEW_FILES = (
    BUNDLE_DIR / "price_updates_review.csv",
    BUNDLE_DIR / "price_updates_review_002.csv",
)
MANUAL_FILE = BUNDLE_DIR / "gpt_manual_price_actions_20260728.csv"
MANIFEST_FILE = BUNDLE_DIR / "migration_manifest.json"


@dataclass(frozen=True)
class PriceAction:
    legacy_id: int
    action: str
    source_file: str
    source_row: int
    brand: str
    product_name: str
    confirmed_sku: str
    price_cny: float | None
    confidence: float
    source_summary: str
    requires_manual_review: bool


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def load_actions() -> list[PriceAction]:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    if manifest.get("migration_version") != MIGRATION_VERSION:
        raise RuntimeError("补价迁移 manifest 版本不匹配")
    missing_rows = _read_csv(MISSING_FILE, "\t")
    identity_by_id = {int(row["id"]): row for row in missing_rows}
    actions: dict[int, PriceAction] = {}
    for path in REVIEW_FILES:
        for row in _read_csv(path):
            if _text(row.get("status")) != "ok":
                continue
            legacy_id = int(row["id"])
            identity = identity_by_id[legacy_id]
            actions[legacy_id] = PriceAction(
                legacy_id=legacy_id,
                action="update_price",
                source_file=_text(identity.get("source_file")),
                source_row=int(identity["source_row"]),
                brand=_text(row.get("brand")),
                product_name=_text(row.get("product_name")),
                confirmed_sku=_text(row.get("confirmed_sku")),
                price_cny=_float(row.get("price_cny")),
                confidence=_float(row.get("confidence")),
                source_summary=_text(row.get("source_summary")),
                requires_manual_review=True,
            )
    for row in _read_csv(MANUAL_FILE):
        legacy_id = int(row["id"])
        identity = identity_by_id[legacy_id]
        action = _text(row.get("action"))
        actions[legacy_id] = PriceAction(
            legacy_id=legacy_id,
            action=action,
            source_file=_text(identity.get("source_file")),
            source_row=int(identity["source_row"]),
            brand=_text(row.get("brand")),
            product_name=_text(row.get("product_name")),
            confirmed_sku=_text(row.get("confirmed_sku")),
            price_cny=_float(row.get("price_cny")) if action == "update_price" else None,
            confidence=1.0 if _text(row.get("status")) == "高置信度" else 0.75,
            source_summary=_text(row.get("source_summary")),
            requires_manual_review=_text(row.get("auto_write")) != "是",
        )
    result = sorted(actions.values(), key=lambda item: (item.source_file, item.source_row))
    updates = sum(item.action == "update_price" for item in result)
    deletes = sum(item.action.startswith("delete") for item in result)
    expected = manifest.get("expected") if isinstance(manifest.get("expected"), dict) else {}
    if updates != int(expected.get("updates") or 0) or deletes != int(expected.get("deletes") or 0):
        raise RuntimeError(f"迁移清单数量异常：updates={updates}, deletes={deletes}")
    return result


def _identity_matches(product: Product, action: PriceAction) -> bool:
    if action.brand and _text(product.brand).lower() != action.brand.lower():
        return False
    if action.confirmed_sku and _text(product.confirmed_sku).lower() != action.confirmed_sku.lower():
        return False
    return not action.product_name or _text(product.product_name) == action.product_name


def apply_database(actions: list[PriceAction], *, commit: bool) -> dict[str, int]:
    counts = {"matched": 0, "updated": 0, "deleted": 0, "deactivated_incomplete": 0, "skipped": 0, "conflicts": 0, "not_found": 0}
    with SessionLocal() as db:
        for action in actions:
            products = list(
                db.scalars(
                    select(Product).where(
                        Product.source_file == action.source_file,
                        Product.source_row == action.source_row,
                    )
                )
            )
            if not products:
                if action.action.startswith("delete"):
                    counts["skipped"] += 1
                else:
                    counts["not_found"] += 1
                continue
            if len(products) != 1 or not _identity_matches(products[0], action):
                counts["conflicts"] += 1
                continue
            product = products[0]
            counts["matched"] += 1
            if action.action.startswith("delete"):
                db.delete(product)
                counts["deleted"] += 1
                continue
            if product.price_cny is not None:
                counts["skipped"] += 1
                continue
            product.price_cny = float(action.price_cny or 0)
            specs = dict(product.specifications or {})
            specs["_price_enrichment"] = {
                "migration_version": MIGRATION_VERSION,
                "price_cny": product.price_cny,
                "currency": "CNY",
                "confidence": action.confidence,
                "source_summary": action.source_summary,
                "requires_manual_review": action.requires_manual_review,
                "provider": "reviewed_price_migration",
                "updated_at": utc_now_iso(),
            }
            product.specifications = specs
            product.quality_status = "complete"
            counts["updated"] += 1
        incomplete_count = int(
            db.scalar(
                select(func.count()).select_from(Product).where(
                    Product.is_active.is_(True),
                    Product.product_name.is_(None),
                )
            )
            or 0
        )
        if incomplete_count:
            db.execute(
                update(Product)
                .where(Product.is_active.is_(True), Product.product_name.is_(None))
                .values(is_active=False, quality_status="invalid")
            )
            counts["deactivated_incomplete"] = incomplete_count
        if counts["conflicts"] or counts["not_found"]:
            db.rollback()
            raise RuntimeError(f"迁移身份检查失败，未写入数据库：{counts}")
        if commit:
            db.commit()
        else:
            db.rollback()
    return counts


def sync_seed(actions: list[PriceAction]) -> dict[str, int]:
    by_location = {(item.source_file, item.source_row): item for item in actions}
    counts = {"updated": 0, "marked_deleted": 0, "conflicts": 0, "not_found": len(actions)}
    for file_name in sorted({item.source_file for item in actions}):
        path = ROOT / "data_seed" / file_name
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for row_number, line in enumerate(lines, 1):
            action = by_location.get((file_name, row_number))
            if action is None:
                continue
            data = json.loads(line)
            if (
                (action.brand and _text(data.get("brand")).lower() != action.brand.lower())
                or (action.confirmed_sku and _text(data.get("confirmed_sku")).lower() != action.confirmed_sku.lower())
            ):
                counts["conflicts"] += 1
                continue
            counts["not_found"] -= 1
            if action.action.startswith("delete"):
                data["_migration_deleted"] = True
                data["_migration_version"] = MIGRATION_VERSION
                counts["marked_deleted"] += 1
            else:
                data["price_cny"] = action.price_cny
                data["_price_enrichment"] = {
                    "migration_version": MIGRATION_VERSION,
                    "confidence": action.confidence,
                    "source_summary": action.source_summary,
                    "requires_manual_review": action.requires_manual_review,
                }
                counts["updated"] += 1
            lines[row_number - 1] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            changed = True
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if counts["conflicts"] or counts["not_found"]:
        raise RuntimeError(f"种子同步身份检查失败：{counts}")
    return counts


def verify_database() -> dict[str, int]:
    with SessionLocal() as db:
        active_missing = int(
            db.scalar(
                select(func.count()).select_from(Product).where(
                    Product.is_active.is_(True),
                    Product.price_cny.is_(None),
                )
            )
            or 0
        )
        flyco_price = db.scalar(
            select(Product.price_cny).where(
                Product.brand == "飞科",
                Product.confirmed_sku == "FS891",
            )
        )
    if active_missing != 0 or float(flyco_price or 0) != 199.0:
        raise RuntimeError(f"价格完整性检查失败：active_missing={active_missing}, flyco_fs891={flyco_price}")
    return {"active_missing": active_missing, "flyco_fs891": int(float(flyco_price))}


def main() -> int:
    parser = argparse.ArgumentParser(description="应用 2026-07-28 已审核产品价格迁移。")
    parser.add_argument("--apply-db", action="store_true", help="提交数据库迁移；不指定时仅校验并回滚。")
    parser.add_argument("--sync-seed", action="store_true", help="把审核价格机械同步回 JSONL 种子。")
    parser.add_argument("--verify", action="store_true", help="验证有效产品无缺价且飞科 FS891=199。")
    args = parser.parse_args()
    actions = load_actions()
    print(json.dumps({"migration_version": MIGRATION_VERSION, "actions": len(actions)}, ensure_ascii=False))
    if args.sync_seed:
        print(json.dumps({"seed": sync_seed(actions)}, ensure_ascii=False))
    if args.apply_db or (not args.sync_seed and not args.verify):
        print(json.dumps({"database": apply_database(actions, commit=args.apply_db)}, ensure_ascii=False))
    if args.verify:
        print(json.dumps({"verify": verify_database()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
