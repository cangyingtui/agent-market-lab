"""Load real sales statistics from order.csv aggregation for market share and brand scoring.

This module replaces synthetic seed-based calculations with actual transaction data.
Usage:
    from engine.sales_lookup import lookup_product_share, lookup_brand_score, match_category
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

# Look in engine/ directory first (Docker-friendly), fall back to project-root data/
_JSON_PATH = Path(__file__).resolve().parent / "sales_stats.json"
if not _JSON_PATH.exists():
    _JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "sales_stats.json"

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        _cache = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _cache = {}
    return _cache


def reload() -> dict:
    """Force reload (useful after regenerating sales_stats.json)."""
    global _cache
    _cache = None
    return _load()


def _best_match(name: str, candidates: list[str], threshold: float = 0.45) -> str | None:
    """Fuzzy match a name against a list of candidates. Returns the best match or None."""
    if not name or not candidates:
        return None
    name_lower = name.lower().strip()
    # Exact match
    for c in candidates:
        if c.lower().strip() == name_lower:
            return c
    # Substring match
    for c in candidates:
        c_lower = c.lower().strip()
        if name_lower in c_lower or c_lower in name_lower:
            return c
    # Sequence similarity
    best_score = 0.0
    best_candidate = None
    for c in candidates:
        c_lower = c.lower().strip()
        score = SequenceMatcher(None, name_lower, c_lower).ratio()
        if score > best_score:
            best_score = score
            best_candidate = c
    return best_candidate if best_score >= threshold else None


def match_category(product_definition: dict) -> str | None:
    """Match a product definition to one of the 5 sales-data categories.

    Checks subcategory first, then category, then product_name keywords against
    known brands/products.
    """
    stats = _load()
    known = list(stats.get("product_shares", {}).keys())
    if not known:
        return None

    subcat = str(product_definition.get("subcategory") or "").strip()
    cat = str(product_definition.get("category") or "").strip()

    # Direct match
    for candidate in (subcat, cat):
        if not candidate:
            continue
        for k in known:
            if candidate == k:
                return k
            if candidate in k or k in candidate:
                return k

    # Try matching via product name / brand against known products
    product_name = str(product_definition.get("product_name") or product_definition.get("name") or "").strip()
    brand = str(product_definition.get("brand") or "").strip()
    for k in known:
        products = stats["product_shares"].get(k, {})
        for pname, pdata in products.items():
            if brand and brand.lower() in str(pdata.get("brand", "")).lower():
                return k
            if product_name and _best_match(product_name, [pname], threshold=0.35):
                return k

    return None


def lookup_product_share(product_name: str, brand: str, category: str | None) -> dict | None:
    """Look up a product's real market share from sales data.

    Returns {share_qty, share_rev, total_qty, total_rev, brand} or None if not found.
    """
    stats = _load()
    product_shares = stats.get("product_shares", {})
    if not category or category not in product_shares:
        return None

    cat_products = product_shares[category]
    candidates = list(cat_products.keys())

    # Try exact or fuzzy match on product name
    matched = _best_match(product_name, candidates, threshold=0.4)
    if matched:
        return cat_products[matched]

    # Try matching by brand
    if brand:
        brand_lower = brand.lower().strip()
        for pname, pdata in cat_products.items():
            if brand_lower in str(pdata.get("brand", "")).lower():
                return pdata

    return None


def lookup_brand_score(brand: str, category: str | None) -> float | None:
    """Look up a brand's radar score (35-95) from real sales data.

    Returns the radar_score or None if not found.
    """
    if not brand or not category:
        return None
    stats = _load()
    brand_shares = stats.get("brand_shares", {})
    cat_brands = brand_shares.get(category, {})
    if not cat_brands:
        return None

    brand_lower = brand.lower().strip()
    for bname, bdata in cat_brands.items():
        if brand_lower == bname.lower().strip():
            return bdata.get("radar_score")
        if brand_lower in bname.lower() or bname.lower() in brand_lower:
            return bdata.get("radar_score")

    # Try SequenceMatcher as last resort
    best_score = 0.0
    best_radar = None
    for bname, bdata in cat_brands.items():
        score = SequenceMatcher(None, brand_lower, bname.lower()).ratio()
        if score > best_score and score >= 0.55:
            best_score = score
            best_radar = bdata.get("radar_score")
    return best_radar


def category_product_list(category: str) -> list[dict]:
    """Return all products in a category with their real shares."""
    stats = _load()
    product_shares = stats.get("product_shares", {})
    if category not in product_shares:
        return []
    return [
        {"product_name": name, **data}
        for name, data in product_shares[category].items()
    ]
