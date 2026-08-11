from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import select

from app.config import settings
from app.openai_compat import create_openai_client
from app.database import SessionLocal
from app.models import Product
from app.time_utils import utc_now_iso


logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        text = value.replace(",", "").replace("￥", "").strip()
        match = re.search(r"\d+(?:\.\d+)?", text)
        if match:
            parsed = float(match.group(0))
            return parsed if parsed > 0 else None
    return None


def _json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _client_configured() -> bool:
    return bool(
        settings.price_enrichment_enabled
        and (settings.price_enrichment_api_key or settings.llm_api_key or settings.embedding_api_key)
        and (settings.price_enrichment_api_base or settings.llm_api_base or settings.embedding_api_base)
        and settings.price_enrichment_model
    )


def estimate_product_price(product: Product) -> dict[str, Any] | None:
    if not _client_configured():
        return None

    api_key = settings.price_enrichment_api_key or settings.llm_api_key or settings.embedding_api_key
    base_url = settings.price_enrichment_api_base or settings.llm_api_base or settings.embedding_api_base
    client = create_openai_client(
        api_key=api_key,
        base_url=base_url or None,
        timeout=settings.price_enrichment_timeout_seconds,
    )
    product_name = _text(product.product_name or product.confirmed_sku)
    brand = _text(product.brand)
    category = " / ".join(item for item in (_text(product.category), _text(product.subcategory)) if item)
    prompt = {
        "task": "估算中国市场公开零售价格",
        "product": {
            "brand": brand,
            "name": product_name,
            "category": category,
            "specifications": product.specifications or {},
        },
        "requirements": [
            "请优先参考公开电商、品牌官网或可信资讯中的近期人民币价格。",
            "只返回 JSON，不要输出解释性文本。",
            "字段固定为 price_cny、currency、source_summary、confidence。",
            "price_cny 为单个数字，不要返回价格区间；如果只能找到区间，取主流成交价或中位数。",
            "confidence 为 0-1，低于 0.65 表示不建议写入数据库。",
        ],
    }
    messages = [
        {"role": "system", "content": "你是谨慎的商品价格补全助手，只根据公开资料估算价格。"},
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, default=str)},
    ]
    kwargs = {
        "model": settings.price_enrichment_model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        response = client.chat.completions.create(**kwargs, extra_body={"enable_search": True})
    except TypeError:
        response = client.chat.completions.create(**kwargs)
    except Exception:
        logger.exception("product_price_enrichment_request_failed", extra={"product_id": product.id})
        return None

    content = response.choices[0].message.content or ""
    data = _json_from_text(content)
    price = _number(data.get("price_cny") or data.get("price") or data.get("estimated_price"))
    confidence = _number(data.get("confidence"))
    if confidence is None:
        confidence = 0.0
    if price is None:
        return None
    return {
        "price_cny": round(price, 2),
        "currency": _text(data.get("currency")) or "CNY",
        "source_summary": _text(data.get("source_summary") or data.get("source") or "公开资料估算"),
        "confidence": max(0.0, min(1.0, confidence)),
    }


def enrich_product_prices_by_ids(product_ids: list[int]) -> int:
    if not _client_configured() or not product_ids:
        return 0
    unique_ids = list(dict.fromkeys(int(item) for item in product_ids if int(item) > 0))
    if not unique_ids:
        return 0

    updated = 0
    with SessionLocal() as db:
        products = list(
            db.scalars(
                select(Product).where(
                    Product.id.in_(unique_ids),
                    Product.is_active.is_(True),
                    Product.price_cny.is_(None),
                )
            )
        )
        for product in products:
            estimate = estimate_product_price(product)
            if not estimate:
                continue
            confidence = float(estimate.get("confidence") or 0)
            if confidence < settings.price_enrichment_min_confidence:
                logger.info(
                    "product_price_enrichment_low_confidence",
                    extra={"product_id": product.id, "confidence": confidence},
                )
                continue
            product.price_cny = float(estimate["price_cny"])
            specs = dict(product.specifications or {})
            specs["_price_enrichment"] = {
                **estimate,
                "provider": "bailian_openai_compatible",
                "updated_at": utc_now_iso(),
                "requires_manual_review": True,
            }
            product.specifications = specs
            updated += 1
        if updated:
            db.commit()
    return updated


def enqueue_product_price_enrichment(background_tasks: BackgroundTasks, product_ids: list[int]) -> int:
    if not settings.price_enrichment_write_master or not _client_configured() or not product_ids:
        return 0
    limited = list(dict.fromkeys(product_ids))[: settings.price_enrichment_max_items_per_request]
    if not limited:
        return 0
    background_tasks.add_task(enrich_product_prices_by_ids, limited)
    return len(limited)
