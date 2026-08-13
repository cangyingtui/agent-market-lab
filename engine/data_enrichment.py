from __future__ import annotations

import json
import hashlib
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.openai_compat import create_openai_client
from app.redis_client import redis_json_get, redis_json_set
from engine.evidence_utils import PRODUCT_EVIDENCE_KEYS, evidence_items
from app.time_utils import utc_now_iso


PROMPT_VERSION = "data_enrichment_v0.2"


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
        snippets = [
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "content": safe_text(row.get("content"))[:800],
            }
            for row in results
            if isinstance(row, dict)
        ]
        client = create_openai_client(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base or None,
            timeout=settings.llm_timeout_seconds,
        )
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


def _parse_json_payload(text: str) -> dict[str, Any] | None:
    text = safe_text(text)
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _public_evidence_api_key() -> str:
    for value in (
        settings.public_evidence_api_key,
        settings.price_enrichment_api_key,
        settings.embedding_api_key,
    ):
        text = safe_text(value)
        if text and text.lower() not in {"replace-this", "replace-this-if-enabled"}:
            return text
    return ""


def _selected_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = safe_text(item.get("name") or item.get("strategy") or item.get("scene"))
            else:
                name = safe_text(item)
            if name:
                result.append(name)
        return list(dict.fromkeys(result))
    text = safe_text(value)
    return [text] if text else []


def _public_query_limit(plan_type: str) -> int:
    if safe_text(plan_type).lower() == "pro":
        return max(0, settings.public_evidence_pro_query_limit)
    return max(0, settings.public_evidence_basic_query_limit)


def build_public_evidence_queries(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    plan_type: str,
) -> list[dict[str, Any]]:
    product = snapshot.get("product_definition") if isinstance(snapshot.get("product_definition"), dict) else {}
    market = snapshot.get("market_config") if isinstance(snapshot.get("market_config"), dict) else {}
    product_name = safe_text(product.get("product_name") or product.get("name") or snapshot.get("project_name"))
    category = safe_text(product.get("category"))
    subcategory = safe_text(product.get("subcategory"))
    brand = safe_text(product.get("brand"))
    competitors = needs_enrichment_items(snapshot, evidence)[:6]
    strategies = _selected_strings(market.get("strategies") or market.get("strategy"))
    scenes = _selected_strings(market.get("scenes") or market.get("scene"))
    query_limit = _public_query_limit(plan_type)

    queries: list[dict[str, Any]] = []
    if competitors:
        competitor_names = [
            " ".join(part for part in (safe_text(item.get("brand")), safe_text(item.get("product_name"))) if part)
            for item in competitors
        ]
        queries.append(
            {
                "topic": "竞品价格与规格公开资料",
                "evidence_type": "competitor_price",
                "related_step": "step2",
                "usable_for": ["competitor_analysis", "pricing_analysis"],
                "query": (
                    f"{subcategory or category} 竞品 价格 规格 参数 官网 电商 "
                    f"{'；'.join(name for name in competitor_names if name)}"
                ).strip(),
                "known_context": {
                    "product_name": product_name,
                    "brand": brand,
                    "category": category,
                    "subcategory": subcategory,
                    "items": competitors,
                },
            }
        )
    if strategies:
        queries.append(
            {
                "topic": "营销策略公开案例",
                "evidence_type": "strategy_case",
                "related_step": "step2",
                "usable_for": ["strategy_analysis", "strategy_roi"],
                "query": f"{subcategory or category} {' '.join(strategies)} 营销策略 案例 转化 用户反馈",
                "known_context": {
                    "product_name": product_name,
                    "category": category,
                    "subcategory": subcategory,
                    "strategies": strategies,
                    "strategy_details": market.get("strategy_details") if isinstance(market.get("strategy_details"), dict) else {},
                },
            }
        )
    if scenes:
        queries.append(
            {
                "topic": "使用场景痛点与购买动机",
                "evidence_type": "scene_pain_point",
                "related_step": "step2",
                "usable_for": ["target_segments", "purchase_model", "scenario_analysis"],
                "query": f"{subcategory or category} {' '.join(scenes)} 使用场景 痛点 购买动机 用户关注点",
                "known_context": {
                    "product_name": product_name,
                    "category": category,
                    "subcategory": subcategory,
                    "scenes": scenes,
                    "scene_details": market.get("scene_details") if isinstance(market.get("scene_details"), dict) else {},
                },
            }
        )
    if category or subcategory or product_name:
        queries.append(
            {
                "topic": "品类价格带与市场趋势",
                "evidence_type": "market_trend",
                "related_step": "step1",
                "usable_for": ["pricing_analysis", "market_overview", "risk_warnings"],
                "query": f"{brand} {product_name} {category} {subcategory} 中国市场 价格带 趋势 用户关注点".strip(),
                "known_context": {
                    "product_name": product_name,
                    "brand": brand,
                    "category": category,
                    "subcategory": subcategory,
                    "price_cny": product.get("price_cny") or product.get("price"),
                },
            }
        )
    return queries[:query_limit]


def _public_cache_key(query_payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "provider": settings.public_evidence_provider,
            "model": settings.public_evidence_model,
            "query": query_payload.get("query"),
            "topic": query_payload.get("topic"),
            "type": query_payload.get("evidence_type"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "public_evidence:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(query_payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        value = redis_json_get(_public_cache_key(query_payload))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _cache_set(query_payload: dict[str, Any], value: dict[str, Any]) -> None:
    ttl = max(60, settings.public_evidence_cache_ttl_hours * 3600)
    try:
        redis_json_set(_public_cache_key(query_payload), value, ex=ttl)
    except Exception:
        return


def normalize_public_evidence_card(card: dict[str, Any], query_payload: dict[str, Any]) -> dict[str, Any]:
    source_urls = card.get("source_urls")
    if not isinstance(source_urls, list):
        source_urls = []
    urls = [safe_text(item) for item in source_urls if safe_text(item)]
    confidence = safe_float(card.get("confidence"))
    if confidence is None:
        confidence = 0.45 if urls else 0.3
    if confidence > 1:
        confidence = confidence / 100
    confidence = max(0.0, min(float(confidence), 1.0))
    extracted_products = card.get("extracted_products")
    if not isinstance(extracted_products, list):
        extracted = card.get("extracted")
        extracted_products = [extracted] if isinstance(extracted, dict) else []
    return {
        "topic": safe_text(card.get("topic") or query_payload.get("topic")),
        "summary": safe_text(card.get("summary") or card.get("answer") or card.get("content"))[:1200],
        "source_urls": urls[:6],
        "related_step": safe_text(card.get("related_step") or query_payload.get("related_step")),
        "confidence": confidence,
        "evidence_type": safe_text(card.get("evidence_type") or query_payload.get("evidence_type") or "market_trend"),
        "usable_for": card.get("usable_for") if isinstance(card.get("usable_for"), list) else query_payload.get("usable_for") or [],
        "risk_note": safe_text(card.get("risk_note") or "公开资料可能存在时效和渠道差异，建议人工复核。")[:500],
        "extracted_products": [item for item in extracted_products if isinstance(item, dict)][:8],
        "query": query_payload.get("query"),
        "provider": settings.public_evidence_provider,
        "prompt_version": PROMPT_VERSION,
        "created_at": utc_now_iso(),
    }


def fallback_public_evidence_card(query_payload: dict[str, Any], raw_text: str = "") -> dict[str, Any]:
    context = query_payload.get("known_context") if isinstance(query_payload.get("known_context"), dict) else {}
    products: list[dict[str, Any]] = []
    for item in (context.get("items") if isinstance(context.get("items"), list) else []):
        if not isinstance(item, dict):
            continue
        products.append(
            {
                "product_id": item.get("id"),
                "brand": item.get("brand"),
                "product_name": item.get("product_name"),
                "price_cny": extract_price(raw_text),
                "specifications": item.get("specifications") if isinstance(item.get("specifications"), dict) else {},
            }
        )
    summary = safe_text(raw_text)[:600]
    if not summary:
        if query_payload.get("evidence_type") == "strategy_case":
            summary = "公开资料补充未返回稳定结论；本轮策略分析将基于已填写配置和仿真结果生成。"
        elif query_payload.get("evidence_type") == "scene_pain_point":
            summary = "公开资料补充未返回稳定结论；本轮场景分析将基于已填写场景和目标客群生成。"
        else:
            summary = "公开资料补充未返回稳定结论；本轮报告将优先使用本地知识库、结构化竞品和配置数据。"
    return normalize_public_evidence_card(
        {
            "summary": summary,
            "source_urls": [],
            "confidence": 0.25,
            "risk_note": "公开资料覆盖有限，已降级为本地规则化证据。",
            "extracted_products": products,
        },
        query_payload,
    )


def bailian_public_search(query_payload: dict[str, Any]) -> dict[str, Any]:
    cached = _cache_get(query_payload)
    if cached:
        cached["cache_hit"] = True
        return cached

    api_key = _public_evidence_api_key()
    if not api_key:
        card = fallback_public_evidence_card(query_payload)
        card["status"] = "skipped"
        card["reason"] = "PUBLIC_EVIDENCE_API_KEY is empty"
        return card

    try:
        client = create_openai_client(
            api_key=api_key,
            base_url=settings.public_evidence_api_base or None,
            timeout=settings.public_evidence_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=settings.public_evidence_model,
            temperature=0,
            extra_body={"enable_search": True},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是公开资料检索助手。必须联网搜索，但只输出 JSON。"
                        "不要编造来源 URL；无法确认时 source_urls 留空。"
                        "如果涉及价格，请标注为估算价格并提醒人工复核。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query_payload.get("query"),
                            "topic": query_payload.get("topic"),
                            "evidence_type": query_payload.get("evidence_type"),
                            "related_step": query_payload.get("related_step"),
                            "usable_for": query_payload.get("usable_for"),
                            "known_context": query_payload.get("known_context"),
                            "required_schema": {
                                "topic": "string",
                                "summary": "string",
                                "source_urls": ["string"],
                                "related_step": "step1|step2|step3|step4",
                                "confidence": "0-1",
                                "evidence_type": "competitor_price|strategy_case|scene_pain_point|market_trend|user_concern",
                                "usable_for": ["string"],
                                "risk_note": "string",
                                "extracted_products": [
                                    {
                                        "product_id": "string|null",
                                        "brand": "string|null",
                                        "product_name": "string|null",
                                        "price_cny": "number|null",
                                        "specifications": "object",
                                    }
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_payload(content)
        card = normalize_public_evidence_card(parsed or {"summary": content}, query_payload)
        card["raw_response_truncated"] = content[:2000]
        card["status"] = "completed"
        _cache_set(query_payload, card)
        return card
    except Exception as exc:
        card = fallback_public_evidence_card(query_payload)
        card["status"] = "fallback"
        card["error_class"] = exc.__class__.__name__
        card["error"] = str(exc)[:300]
        return card


def normalize_cards_with_deepseek(cards: list[dict[str, Any]], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if not cards or not settings.llm_api_key:
        return cards
    try:
        client = create_openai_client(
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base or None,
            timeout=min(settings.llm_timeout_seconds, 20),
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是证据整理模型，不联网。请把公开资料卡片整理为统一 evidence cards。"
                        "保留来源、指出冲突和风险，不要新增没有来源的事实。只输出 JSON。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "snapshot_brief": {
                                "product_definition": snapshot.get("product_definition"),
                                "market_config": snapshot.get("market_config"),
                            },
                            "cards": cards,
                            "required_schema": {
                                "cards": [
                                    {
                                        "topic": "string",
                                        "summary": "string",
                                        "source_urls": ["string"],
                                        "related_step": "string",
                                        "confidence": "0-1",
                                        "evidence_type": "string",
                                        "usable_for": ["string"],
                                        "risk_note": "string",
                                        "extracted_products": [],
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    )[:18000],
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = _parse_json_payload(content) or {}
        normalized = parsed.get("cards") if isinstance(parsed.get("cards"), list) else []
        result: list[dict[str, Any]] = []
        for index, item in enumerate(normalized):
            if isinstance(item, dict):
                base_query = {"topic": cards[min(index, len(cards) - 1)].get("topic"), "evidence_type": cards[min(index, len(cards) - 1)].get("evidence_type")}
                result.append(normalize_public_evidence_card(item, base_query))
        if result:
            return result
    except Exception:
        return cards
    return cards


def public_cards_to_candidates(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for card in cards:
        if card.get("evidence_type") != "competitor_price":
            continue
        for item in card.get("extracted_products") if isinstance(card.get("extracted_products"), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                {
                    "source": "public_evidence",
                    "provider": card.get("provider"),
                    "prompt_version": PROMPT_VERSION,
                    "query": card.get("query"),
                    "product_id": item.get("product_id") or item.get("id"),
                    "product_name": item.get("product_name") or item.get("name"),
                    "brand": item.get("brand"),
                    "price_cny": item.get("price_cny"),
                    "specifications": item.get("specifications") if isinstance(item.get("specifications"), dict) else {},
                    "source_urls": card.get("source_urls") or [],
                    "confidence": card.get("confidence") or 0.35,
                    "quality_reasons": [],
                    "raw_summary": card.get("summary"),
                    "status": "public_evidence_candidate",
                    "created_at": utc_now_iso(),
                }
            )
    return candidates


def evidence_cards_to_evidence(cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "public_competitor_evidence": [],
        "public_strategy_evidence": [],
        "public_scene_evidence": [],
        "public_market_evidence": [],
    }
    for index, card in enumerate(cards, 1):
        evidence_type = safe_text(card.get("evidence_type"))
        if evidence_type == "competitor_price":
            group = "public_competitor_evidence"
            source_type = "product_competitor"
        elif evidence_type == "strategy_case":
            group = "public_strategy_evidence"
            source_type = "market_strategy"
        elif evidence_type == "scene_pain_point":
            group = "public_scene_evidence"
            source_type = "market_strategy"
        else:
            group = "public_market_evidence"
            source_type = "market_strategy"
        snippet = safe_text(card.get("summary")) or safe_text(card.get("risk_note"))
        groups[group].append(
            {
                "type": "public_evidence",
                "source": f"public_evidence:{evidence_type or 'market'}:{index}",
                "source_type": source_type,
                "source_category": "公开资料补充",
                "rank": index,
                "score": card.get("confidence") or 0.35,
                "matched_fields": ["public_evidence", evidence_type],
                "snippet": snippet[:600],
                "raw": {
                    "topic": card.get("topic"),
                    "summary": card.get("summary"),
                    "source_urls": card.get("source_urls") or [],
                    "related_step": card.get("related_step"),
                    "confidence": card.get("confidence"),
                    "evidence_type": evidence_type,
                    "usable_for": card.get("usable_for") or [],
                    "risk_note": card.get("risk_note"),
                    "extracted_products": card.get("extracted_products") or [],
                },
            }
        )
    return {key: value for key, value in groups.items() if value}


def _run_bailian_public_evidence(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    plan_type: str,
) -> dict[str, Any]:
    if settings.public_evidence_provider != "bailian":
        return {
            "enabled": True,
            "status": "skipped",
            "reason": f"unsupported provider: {settings.public_evidence_provider}",
            "candidates": [],
            "evidence_cards": [],
        }
    queries = build_public_evidence_queries(snapshot, evidence, plan_type)
    cards: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    started = time.monotonic()
    for query_payload in queries:
        if time.monotonic() - started > max(1, settings.public_evidence_total_timeout_seconds):
            errors.append({"query": query_payload.get("query"), "error": "public evidence total timeout"})
            break
        card = bailian_public_search(query_payload)
        cards.append(card)
        if card.get("error"):
            errors.append({"query": query_payload.get("query"), "error": card.get("error"), "error_class": card.get("error_class")})

    cards = normalize_cards_with_deepseek(cards, snapshot)
    candidates = public_cards_to_candidates(cards)
    price_updates = auto_fill_missing_evidence_prices(evidence, candidates)
    return {
        "enabled": True,
        "status": "completed_with_errors" if errors else "completed",
        "provider": settings.public_evidence_provider,
        "model": settings.public_evidence_model,
        "prompt_version": PROMPT_VERSION,
        "query_count": len(queries),
        "query_limit": _public_query_limit(plan_type),
        "evidence_card_count": len(cards),
        "evidence_cards": cards,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "auto_filled_price_count": len(price_updates),
        "auto_filled_prices": price_updates,
        "errors": errors,
        "created_at": utc_now_iso(),
    }


def _run_tavily_enrichment(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
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


def run_data_enrichment(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    plan_type: str = "basic",
) -> dict[str, Any]:
    if settings.public_evidence_enabled:
        if settings.public_evidence_provider == "tavily":
            return _run_tavily_enrichment(snapshot, evidence)
        return _run_bailian_public_evidence(snapshot, evidence, plan_type)
    return _run_tavily_enrichment(snapshot, evidence)
