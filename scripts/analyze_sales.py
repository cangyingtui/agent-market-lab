"""Derive market share and brand scores from real order.csv transaction data.

Usage:
  python scripts/analyze_sales.py                  # print report
  python scripts/analyze_sales.py --json           # output to stdout
  python scripts/analyze_sales.py --out data/sales_stats.json
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime

ORDER_CSV = "order.csv"


def load_product_sales(path: str = ORDER_CSV):
    """Aggregate total quantity and revenue per product (brand + product_name) per category.

    Returns:
        products: {category: {product_name: {brand, total_qty, total_rev}}}
        brands:   {category: {brand: {total_qty, total_rev}}}
    """
    products: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"brand": "", "total_qty": 0, "total_rev": 0.0}
    ))
    brands: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"total_qty": 0, "total_rev": 0.0}
    ))

    with open(path, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            brand = (row.get("brand") or "").strip()
            cat = (row.get("category") or "").strip()
            product_name = (row.get("product_name") or "").strip()
            if not brand or not cat:
                continue
            qty = int(row.get("quantity", 1))
            amt = float(row.get("amount", 0))

            # Product-level
            key = product_name if product_name else f"{brand}_unknown"
            entry = products[cat][key]
            entry["brand"] = brand
            entry["total_qty"] += qty
            entry["total_rev"] += amt

            # Brand-level (aggregate all products of this brand in this category)
            brands[cat][brand]["total_qty"] += qty
            brands[cat][brand]["total_rev"] += amt

    return products, brands


def compute_market_shares(products, brands):
    """Compute market share percentages within each category.

    Returns:
        product_shares: {category: {product_name: {brand, share_qty, share_rev}}}
        brand_shares:   {category: {brand: {share_qty, share_rev, radar_score}}}
        categories:     list of category names with stats
    """
    product_shares: dict = {}
    brand_shares: dict = {}

    for cat in sorted(products.keys()):
        # Product shares
        total_cat_qty = sum(p["total_qty"] for p in products[cat].values())
        total_cat_rev = sum(p["total_rev"] for p in products[cat].values())

        product_shares[cat] = {}
        for name, data in sorted(products[cat].items(), key=lambda x: x[1]["total_qty"], reverse=True):
            product_shares[cat][name] = {
                "brand": data["brand"],
                "total_qty": data["total_qty"],
                "total_rev": round(data["total_rev"], 2),
                "share_qty": round(data["total_qty"] / total_cat_qty * 100, 2) if total_cat_qty else 0,
                "share_rev": round(data["total_rev"] / total_cat_rev * 100, 2) if total_cat_rev else 0,
            }

        # Brand shares
        total_brand_qty = sum(b["total_qty"] for b in brands[cat].values())
        max_brand_qty = max(b["total_qty"] for b in brands[cat].values()) if brands[cat] else 1
        brand_shares[cat] = {}
        for brand_name, data in sorted(brands[cat].items(), key=lambda x: x[1]["total_qty"], reverse=True):
            brand_shares[cat][brand_name] = {
                "total_qty": data["total_qty"],
                "total_rev": round(data["total_rev"], 2),
                "share_qty": round(data["total_qty"] / total_brand_qty * 100, 2) if total_brand_qty else 0,
                "share_rev": round(data["total_rev"] / total_cat_rev * 100, 2) if total_cat_rev else 0,
                "radar_score": round(35 + data["total_qty"] / max_brand_qty * 60, 1),
            }

    # Category list
    category_list = []
    for cat in sorted(products.keys()):
        total_qty = sum(p["total_qty"] for p in products[cat].values())
        category_list.append({
            "name": cat,
            "product_count": len(products[cat]),
            "brand_count": len(brands.get(cat, {})),
            "total_orders": total_qty,
        })

    return product_shares, brand_shares, category_list


def print_report(product_shares, brand_shares, category_list):
    """Human-readable report."""
    for cat_info in category_list:
        cat = cat_info["name"]
        print(f"=== {cat} ({cat_info['product_count']} products, {cat_info['brand_count']} brands, {cat_info['total_orders']:,} orders) ===")
        print(f"{'Product':<30} {'Brand':<12} {'Qty':>8} {'Share%':>8} {'Revenue':>12}")
        print("-" * 78)
        for name, data in sorted(product_shares[cat].items(), key=lambda x: x[1]["total_qty"], reverse=True):
            print(f"{name:<30} {data['brand']:<12} {data['total_qty']:>8,} {data['share_qty']:>7.1f}% {data['total_rev']:>12,.0f}")
        print()

    print("=== Brand Radar Scores (qty-based, 35-95 range) ===")
    for cat, items in brand_shares.items():
        print(f"\n  {cat}:")
        for brand, data in sorted(items.items(), key=lambda x: x[1]["radar_score"], reverse=True):
            print(f"    {brand:<14} qty={data['total_qty']:>8,}  share={data['share_qty']:>5.1f}%  radar={data['radar_score']}")


def export_json(product_shares, brand_shares, category_list):
    """Export machine-readable JSON."""
    output = {
        "source": "order.csv transaction aggregation",
        "data_period": "2024-01 ~ 2025-01",
        "total_orders": sum(c["total_orders"] for c in category_list),
        "categories": category_list,
        "product_shares": product_shares,
        "brand_shares": brand_shares,
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    products, brands = load_product_sales()
    product_shares, brand_shares, category_list = compute_market_shares(products, brands)

    out_path = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--out" and i + 1 < len(args):
            out_path = args[i + 1]

    if "--json" in args or out_path:
        js = export_json(product_shares, brand_shares, category_list)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(js)
            print(f"Written to {out_path}")
        else:
            print(js)
    else:
        print_report(product_shares, brand_shares, category_list)
