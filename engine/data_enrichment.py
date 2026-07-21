from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings
from engine.evidence_utils import PRODUCT_EVIDENCE_KEYS, evidence_items
from app.time_utils import utc_now_iso


PROMPT_VERSION = "data_enrichment_v0.1"


PRICE_PATTERN = re.compile(r"(?:￥|¥|RMB|CNY)?\s*([1-9]\d{2,6}(?:\.\d{1,2})?)\s*(?:元|块|rmb|cny)?", re.I)


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def quality_reasons(item: dict[str, Any]) -> list[str]:
    specs = item.get("specifications") if isinstance(item.get("specifications"), dict) else {}
    reasons: list[str] = []
    name = safe_text(item.get("product_name") or item.get("name") or item.get("confirmed_sku"))
    brand = safe_text(item.get("brand"))
    price = safe_float(item.get("price_cny") or item.get("price"))
    if not name or name in {"竞品", "同类竞品"}:
        reasons.append("missing_product_name")
    if not brand or brand in {"未知品牌", "泛竞品"}:
        reasons.append("missing_brand")
    if price is None:
        reasons.append("missing_price")
    if not specs:
        reasons.append("missing_specs")
    return reasons


def configured_competitors(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    rows = market.get("competitors") if isinstance(market.get("competitors"), list) else []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows, 1):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "id": item.get("id") or item.get("product_id") or f"configured_{index}",
                "product_name": item.get("product_name") or item.get("name") or item.get("custom_name"),
                "brand": item.get("brand"),
                "price_cny": item.get("price_cny") or item.get("price"),
                "specifications": item.get("specifications") or item.get("params") or {},
                "source": "market_config",
            }
        )
    return result


def evidence_competitors(evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS):
        if item.get("source_type") != "product_competitor":
            continue
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        result.append(
            {
                "id": raw.get("id") or item.get("source"),
                "product_name": raw.get("product_name") or raw.get("confirmed_sku"),
                "brand": raw.get("brand"),
                "price_cny": raw.get("price_cny"),
                "specifications": raw.get("specifications") if isinstance(raw.get("specifications"), dict) else {},
                "source": item.get("source"),
            }
        )
    return result


def needs_enrichment_items(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for item in [*configured_competitors(snapshot), *evidence_competitors(evidence)]:
        key = safe_text(item.get("id") or item.get("product_name") or item.get("source"))
        if not key or key in seen:
            continue
        reasons = quality_reasons(item)
        if not reasons:
            continue
        seen.add(key)
        items.append({**item, "quality_reasons": reasons})
    return items[: max(0, settings.enrichment_max_items_per_run)]


def build_query(snapshot: dict[str, Any], item: dict[str, Any]) -> str:
    product = snapshot.get("product_definition") if isinstance(snapshot.get("product_definition"), dict) else {}
    parts = [
        safe_text(item.get("brand")),
        safe_text(item.get("product_name")),
        safe_text(product.get("category")),
        safe_text(product.get("subcategory")),
        "价格 规格 参数 官网 电商",
    ]
    query = " ".join(part for part in parts if part)
    return query or "同类产品 价格 规格"


def tavily_search(query: str) -> list[dict[str, Any]]:
    if not settings.enrichment_api_key:
        return []
    response = httpx.post(
        settings.enrichment_api_base,
        json={
            "api_key": settings.enrichment_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") if isinstance(payload, dict) else []
    return results if isinstance(results, list) else []


def extract_price(text: str) -> float | None:
    candidates: list[float] = []
    for match in PRICE_PATTERN.finditer(text):
        value = safe_float(match.group(1))
        if value is not None and 100 <= value <= 200000:
            candidates.append(value)
    return min(candidates) if candidates else None


def regex_extract_candidate(item: dict[str, Any], query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    combined = "\n".join(
        f"{safe_text(row.get('title'))} {safe_text(row.get('content'))}"
        for row in results
        if isinstance(row, dict)
    )
    source_urls = [safe_text(row.get("url")) for row in results if isinstance(row, dict) and row.get("url")]
    price = extract_price(combined)
    specs: dict[str, Any] = {}
    for keyword in ("电池", "续航", "防水", "重量", "屏幕", "电机", "材质", "功率"):
        if keyword in combined:
            specs[keyword] = "网页候选中出现，待人工确认"
    return {
        "source": "web_enrichment",
        "provider": settings.enrichment_provider,
        "prompt_version": PROMPT_VERSION,
        "query": query,
        "product_id": item.get("id"),
        "product_name": item.get("product_name") or "待确认竞品",
        "brand": item.get("brand") or "待确认品牌",
        "price_cny": price,
        "specifications": specs,
        "source_urls": source_urls[:3],
        "confidence": 0.55 if source_urls else 0.2,
        "quality_reasons": item.get("quality_reasons") or [],
        "raw_summary": combined[:1200],
        "status": "candidate_pending_review",
        "created_at": utc_now_iso(),
    }


def llm_extract_candidate(item: dict[str, Any], query: str, results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not settings.llm_api_key or not results:
        return None
    try:
        from openai import OpenAI

        snippets = [
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "content": safe_text(row.get("content"))[:800],
            }
            for row in results
            if isinstance(row, dict)
        ]
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_base or None, timeout=settings.llm_timeout_seconds)
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "你只输出 JSON。请从网页摘要中抽取竞品候选字段，不确定就填 null，不要编造。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "known_item": item,
                            "snippets": snippets,
                            "schema": {
                                "product_name": "string|null",
                                "brand": "string|null",
                                "price_cny": "number|null",
                                "specifications": "object",
                                "confidence": "0-1",
                                "reason": "string",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        text = response.choices[0].message.content or "{}"
        parsed = json.loads(text.strip().strip("`"))
        if not isinstance(parsed, dict):
            return None
        source_urls = [safe_text(row.get("url")) for row in results if isinstance(row, dict) and row.get("url")]
        return {
            "source": "web_enrichment",
            "provider": settings.enrichment_provider,
            "prompt_version": PROMPT_VERSION,
            "query": query,
            "product_id": item.get("id"),
            "product_name": parsed.get("product_name") or item.get("product_name") or "待确认竞品",
            "brand": parsed.get("brand") or item.get("brand") or "待确认品牌",
            "price_cny": parsed.get("price_cny"),
            "specifications": parsed.get("specifications") if isinstance(parsed.get("specifications"), dict) else {},
            "source_urls": source_urls[:3],
            "confidence": max(0.0, min(float(parsed.get("confidence") or 0.5), 1.0)),
            "quality_reasons": item.get("quality_reasons") or [],
            "raw_summary": safe_text(parsed.get("reason"))[:1200],
            "status": "candidate_pending_review",
            "created_at": utc_now_iso(),
        }
    except Exception:
        return None


def candidate_to_evidence(candidate: dict[str, Any], rank: int) -> dict[str, Any]:
    snippet = (
        f"网页候选，待人工确认：{candidate.get('brand') or ''} {candidate.get('product_name') or ''}"
        f"；候选价格：{candidate.get('price_cny') if candidate.get('price_cny') is not None else '未确认'}"
    )
    return {
        "type": "structured_product",
        "source": f"web_enrichment:{candidate.get('product_id') or rank}",
        "source_type": "product_competitor",
        "rank": rank,
        "score": candidate.get("confidence") or 0.4,
        "matched_fields": ["web_enrichment_candidate"],
        "snippet": snippet,
        "raw": {
            "id": candidate.get("product_id") or f"web_{rank}",
            "product_name": candidate.get("product_name"),
            "brand": candidate.get("brand"),
            "price_cny": candidate.get("price_cny"),
            "specifications": candidate.get("specifications") or {},
            "source_urls": candidate.get("source_urls") or [],
            "enrichment_status": candidate.get("status"),
            "needs_human_review": True,
        },
    }


def _candidate_lookup_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        safe_text(candidate.get("product_id")),
        safe_text(candidate.get("brand")).lower(),
        safe_text(candidate.get("product_name")).lower(),
    )


def _evidence_lookup_key(item: dict[str, Any]) -> tuple[str, str, str]:
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    return (
        safe_text(raw.get("id")),
        safe_text(raw.get("brand")).lower(),
        safe_text(raw.get("product_name") or raw.get("confirmed_sku")).lower(),
    )


def auto_fill_missing_evidence_prices(
    evidence: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    priced_candidates = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and safe_float(candidate.get("price_cny")) is not None
    ]
    updates: list[dict[str, Any]] = []
    if not priced_candidates:
        return updates

    by_id = {
        safe_text(candidate.get("product_id")): candidate
        for candidate in priced_candidates
        if safe_text(candidate.get("product_id"))
    }
    by_name = {
        _candidate_lookup_key(candidate)[1:]: candidate
        for candidate in priced_candidates
        if any(_candidate_lookup_key(candidate)[1:])
    }

    for group, items in evidence.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("source_type") != "product_competitor":
                continue
            raw = item.get("raw") if isinstance(item.get("raw"), dict) else None
            if raw is None or safe_float(raw.get("price_cny")) is not None:
                continue
            raw_id, raw_brand, raw_name = _evidence_lookup_key(item)
            candidate = by_id.get(raw_id) or by_name.get((raw_brand, raw_name))
            price = safe_float(candidate.get("price_cny")) if candidate else None
            if price is None:
                continue

            raw["price_cny"] = price
            raw["price_missing"] = False
            raw["price_source"] = "web_enrichment"
            raw["price_source_urls"] = candidate.get("source_urls") or []
            raw["enrichment_status"] = "auto_filled_web_price"
            raw["needs_human_review"] = False
            quality = raw.get("quality") if isinstance(raw.get("quality"), dict) else None
            if quality is not None:
                quality["has_price"] = True
                quality["needs_enrichment"] = not (
                    bool(quality.get("has_name")) and bool(quality.get("has_specs"))
                )
                raw["needs_enrichment"] = quality["needs_enrichment"]
            else:
                raw["needs_enrichment"] = False
            matched_fields = item.get("matched_fields") if isinstance(item.get("matched_fields"), list) else []
            item["matched_fields"] = sorted({*matched_fields, "web_enrichment_price"})
            snippet = safe_text(item.get("snippet"))
            item["snippet"] = (
                snippet.replace("价格未确认", f"价格约{price:.0f}元")
                if "价格未确认" in snippet
                else f"{snippet}；网页补充价格约{price:.0f}元"
            )[:300]
            updates.append(
                {
                    "evidence_group": group,
                    "source": item.get("source"),
                    "product_id": raw_id,
                    "price_cny": price,
                    "source_urls": raw.get("price_source_urls") or [],
                }
            )
    return updates


def run_data_enrichment(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    if not settings.enable_data_enrichment:
        return {"enabled": False, "status": "skipped", "reason": "ENABLE_DATA_ENRICHMENT=false", "candidates": []}
    if settings.enrichment_provider != "tavily":
        return {"enabled": True, "status": "skipped", "reason": f"unsupported provider: {settings.enrichment_provider}", "candidates": []}
    if not settings.enrichment_api_key:
        return {"enabled": True, "status": "skipped", "reason": "ENRICHMENT_API_KEY is empty", "candidates": []}

    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for item in needs_enrichment_items(snapshot, evidence):
        query = build_query(snapshot, item)
        try:
            results = tavily_search(query)
            candidate = llm_extract_candidate(item, query, results) or regex_extract_candidate(item, query, results)
            candidates.append(candidate)
        except Exception as exc:
            errors.append({"query": query, "error_class": exc.__class__.__name__, "error": str(exc)[:300]})
    price_updates = auto_fill_missing_evidence_prices(evidence, candidates)
    return {
        "enabled": True,
        "status": "completed_with_errors" if errors else "completed",
        "provider": settings.enrichment_provider,
        "prompt_version": PROMPT_VERSION,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "auto_filled_price_count": len(price_updates),
        "auto_filled_prices": price_updates,
        "errors": errors,
        "created_at": utc_now_iso(),
    }
