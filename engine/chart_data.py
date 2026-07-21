from __future__ import annotations

import math
from collections import Counter
from typing import Any

from engine.evidence_utils import PRODUCT_EVIDENCE_KEYS, evidence_items


PROMPT_VERSION = "chart_data_v0.1"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return default
    return default


def normalize_percent(rows: list[dict[str, Any]], value_key: str = "seed") -> list[dict[str, Any]]:
    total = sum(max(0.0, safe_float(row.get(value_key))) for row in rows)
    if total <= 0:
        total = float(len(rows) or 1)
        for row in rows:
            row[value_key] = 1
    remaining = 100.0
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index == len(rows) - 1:
            percent = round(remaining, 1)
        else:
            percent = round(max(0.0, safe_float(row.get(value_key))) / total * 100, 1)
            remaining -= percent
        copied = {key: value for key, value in row.items() if key != value_key}
        copied["value"] = percent
        copied["share"] = percent
        result.append(copied)
    return result


def product_name(product: dict[str, Any]) -> str:
    return str(product.get("product_name") or product.get("name") or "本品")


def product_price(product: dict[str, Any]) -> float | None:
    value = product.get("price_cny") or product.get("price")
    parsed = safe_float(value, default=-1)
    return parsed if parsed >= 0 else None


def evidence_competitors(evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    competitors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence_items(evidence, *PRODUCT_EVIDENCE_KEYS):
        if item.get("source_type") != "product_competitor":
            continue
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        key = str(raw.get("id") or item.get("source") or item.get("snippet"))
        if key in seen:
            continue
        seen.add(key)
        competitors.append(
            {
                "id": raw.get("id") or item.get("source"),
                "name": raw.get("product_name") or raw.get("confirmed_sku") or item.get("source") or "竞品",
                "brand": raw.get("brand") or "未知品牌",
                "price": raw.get("price_cny"),
                "specifications": raw.get("specifications") if isinstance(raw.get("specifications"), dict) else {},
                "score": safe_float(item.get("score"), 0.0),
                "source": item.get("source"),
                "snippet": item.get("snippet"),
                "source_urls": raw.get("source_urls") if isinstance(raw.get("source_urls"), list) else [],
                "enrichment_status": raw.get("enrichment_status"),
                "needs_human_review": bool(raw.get("needs_human_review")),
            }
        )
    return competitors


def configured_competitors(market_config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = market_config.get("competitors")
    rows = raw if isinstance(raw, list) else []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(rows, 1):
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "id": item.get("id") or item.get("product_id") or f"configured_{index}",
                "name": item.get("product_name") or item.get("name") or item.get("custom_name") or f"竞品{index}",
                "brand": item.get("brand") or "自定义竞品",
                "price": item.get("price_cny") or item.get("price"),
                "specifications": item.get("specifications") or item.get("params") or {},
                "score": 1.0,
                "source": item.get("source") or "market_config",
                "snippet": item.get("custom_desc") or "",
                "source_urls": item.get("source_urls") if isinstance(item.get("source_urls"), list) else [],
                "enrichment_status": item.get("enrichment_status"),
                "needs_human_review": bool(item.get("needs_human_review")),
            }
        )
    return result


def collect_competitors(snapshot: dict[str, Any], evidence: dict[str, list[dict[str, Any]]], plan_type: str) -> list[dict[str, Any]]:
    market = snapshot.get("market_config") or {}
    rows = evidence_competitors(evidence)
    configured = configured_competitors(market)
    seen = {str(item.get("id")) for item in rows}
    for item in configured:
        if str(item.get("id")) not in seen:
            rows.append(item)
            seen.add(str(item.get("id")))
    if not rows:
        rows.append({"id": "generic", "name": "同类竞品", "brand": "泛竞品", "price": None, "specifications": {}, "score": 0.8})
    return rows[:1] if plan_type == "basic" else rows


def active_params(product: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    raw_params = product.get("params")
    params: list[dict[str, Any]] = []
    if isinstance(raw_params, list):
        for index, item in enumerate(raw_params, 1):
            if not isinstance(item, dict):
                continue
            enabled = bool(item.get("enabled", True))
            if plan_type == "basic" and not enabled:
                continue
            params.append(
                {
                    "id": item.get("id") or f"param_{index}",
                    "raw_name": str(item.get("raw_name") or item.get("name") or f"参数{index}"),
                    "name": str(item.get("label") or item.get("name") or f"参数{index}"),
                    "label": str(item.get("label") or item.get("name") or f"参数{index}"),
                    "value": item.get("value"),
                    "unit": item.get("unit") or "",
                    "weight": safe_float(item.get("weight"), 3.0),
                    "enabled": enabled,
                    "is_preset": bool(item.get("is_preset", True)),
                }
            )
    if not params and isinstance(product.get("specifications"), dict):
        for index, (name, value) in enumerate(product["specifications"].items(), 1):
            params.append(
                {
                    "id": f"spec_{index}",
                    "raw_name": str(name),
                    "name": str(name),
                    "label": str(name),
                    "value": value,
                    "unit": "",
                    "weight": 3.0,
                    "enabled": True,
                    "is_preset": True,
                }
            )
    return params[:3] if plan_type == "basic" else params[:12]


def purchase_intent_rows(aggregation: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    avg = safe_float(aggregation.get("purchase_intent_avg"), 0.0)
    segment_summary = aggregation.get("segment_summary") if isinstance(aggregation.get("segment_summary"), dict) else {}
    if not segment_summary:
        return [{"name": "整体人群", "value": round(avg * 100, 1), "count": 0}]
    return [
        {
            "name": str(segment),
            "value": round(safe_float(data.get("avg_purchase_intent")) * 100, 1) if isinstance(data, dict) else 0,
            "count": int(data.get("count") or 0) if isinstance(data, dict) else 0,
            "ratio": safe_float(data.get("ratio")) if isinstance(data, dict) else 0,
            "weighted_contribution": round(safe_float(data.get("weighted_contribution")) * 100, 1)
            if isinstance(data, dict)
            else 0,
        }
        for segment, data in segment_summary.items()
    ]


def market_share_rows(
    product: dict[str, Any],
    competitors: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> list[dict[str, Any]]:
    avg = clamp(safe_float(aggregation.get("purchase_intent_avg"), 0.5), 0.05, 0.95)
    own_seed = 0.35 + avg
    target_price = product_price(product)
    max_score = max([safe_float(item.get("score"), 0.0) for item in competitors] + [1.0])
    rows = [{"name": product_name(product), "role": "self", "seed": own_seed, "source": "agent_decision"}]
    for item in competitors:
        price = safe_float(item.get("price"), -1)
        price_factor = 1.0
        if target_price and price > 0:
            price_factor = 1.12 if price < target_price else 0.92 if price > target_price else 1.0
        rows.append(
            {
                "name": str(item.get("name") or "竞品"),
                "role": "competitor",
                "seed": max(0.25, safe_float(item.get("score"), 0.5) / max_score) * price_factor,
                "source": item.get("source"),
            }
        )
    return normalize_percent(rows)


def compact_market_share_rows(rows: list[dict[str, Any]], top_competitors: int = 10) -> list[dict[str, Any]]:
    self_rows = [row for row in rows if row.get("role") == "self"]
    competitor_rows = [row for row in rows if row.get("role") != "self"]
    competitor_rows.sort(key=lambda item: safe_float(item.get("share")), reverse=True)
    selected = competitor_rows[:top_competitors]
    rest = competitor_rows[top_competitors:]
    compacted = [*self_rows, *selected]
    if rest:
        other_share = round(sum(safe_float(item.get("share")) for item in rest), 1)
        compacted.append(
            {
                "name": "其他竞品汇总",
                "role": "competitor_other",
                "share": other_share,
                "value": other_share,
                "source": "chart_top_n_compaction",
                "competitor_count": len(rest),
            }
        )
    if compacted:
        delta = round(100 - sum(safe_float(item.get("share")) for item in compacted), 1)
        compacted[-1]["share"] = round(safe_float(compacted[-1].get("share")) + delta, 1)
        compacted[-1]["value"] = compacted[-1]["share"]
    return compacted


def compact_competitor_radar(radar: dict[str, Any], top_competitors: int = 8) -> dict[str, Any]:
    series = radar.get("series") if isinstance(radar.get("series"), list) else []
    self_rows = [row for row in series if isinstance(row, dict) and row.get("role") == "self"]
    competitor_rows = [row for row in series if isinstance(row, dict) and row.get("role") != "self"]
    selected = competitor_rows[:top_competitors]
    rest = competitor_rows[top_competitors:]
    result = {**radar, "series": [*self_rows, *selected]}
    if rest:
        length = len(radar.get("dimensions") or [])
        totals = [0.0] * length
        for row in rest:
            values = row.get("values") if isinstance(row.get("values"), list) else []
            for index in range(length):
                totals[index] += safe_float(values[index] if index < len(values) else 0)
        averaged = [round(value / max(1, len(rest)), 1) for value in totals]
        result["series"].append({"name": "其他竞品均值", "role": "competitor_other", "values": averaged, "competitor_count": len(rest)})
    return result


def competitor_analysis_rows(competitors: list[dict[str, Any]], market_share_full: list[dict[str, Any]]) -> list[dict[str, Any]]:
    share_by_name: dict[str, float] = {
        str(row.get("name")): safe_float(row.get("share"))
        for row in market_share_full
        if row.get("role") == "competitor"
    }
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(competitors, 1):
        specs = item.get("specifications") if isinstance(item.get("specifications"), dict) else {}
        price = item.get("price")
        rows.append(
            {
                "rank": index,
                "name": str(item.get("name") or "竞品"),
                "brand": item.get("brand") or "未知品牌",
                "price": price,
                "price_status": "已确认" if product_price({"price_cny": price}) is not None else "价格未确认",
                "spec_count": len(specs),
                "estimated_share": share_by_name.get(str(item.get("name") or "竞品"), 0),
                "source": item.get("source"),
                "source_urls": item.get("source_urls") or [],
                "enrichment_status": item.get("enrichment_status") or ("candidate_pending_review" if item.get("needs_human_review") else None),
                "review_note": "网页候选，待人工确认" if item.get("needs_human_review") else "",
                "snippet": item.get("snippet"),
            }
        )
    return rows


def feature_richness(specs: dict[str, Any]) -> float:
    return clamp(55 + len(specs) * 8, 40, 95)


def price_competitiveness(price: float | None, reference: float | None) -> float:
    if price is None or reference is None or price <= 0 or reference <= 0:
        return 60
    ratio = price / reference
    if ratio <= 0.8:
        return 88
    if ratio <= 1.0:
        return 78
    if ratio <= 1.2:
        return 62
    return 48


def competitor_radar_rows(
    product: dict[str, Any],
    competitors: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    dimensions = ["功能丰富度", "价格竞争力", "品牌影响力", "用户体验", "渠道覆盖"]
    target_price = product_price(product)
    avg_price = None
    priced = [safe_float(item.get("price"), -1) for item in competitors if safe_float(item.get("price"), -1) > 0]
    if priced:
        avg_price = sum(priced) / len(priced)
    product_specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    avg_intent = safe_float(aggregation.get("purchase_intent_avg"), 0.5)
    series = [
        {
            "name": product_name(product),
            "role": "self",
            "values": [
                feature_richness(product_specs),
                price_competitiveness(target_price, avg_price),
                72 if product.get("brand") else 58,
                round(clamp(avg_intent * 100 + 12, 35, 95), 1),
                68,
            ],
        }
    ]
    for item in competitors:
        specs = item.get("specifications") if isinstance(item.get("specifications"), dict) else {}
        series.append(
            {
                "name": str(item.get("name") or "竞品"),
                "role": "competitor",
                "values": [
                    feature_richness(specs),
                    price_competitiveness(product_price({"price_cny": item.get("price")}), target_price),
                    66 if item.get("brand") and item.get("brand") != "未知品牌" else 55,
                    round(clamp(58 + safe_float(item.get("score"), 0.5) * 4, 35, 90), 1),
                    60,
                ],
            }
        )
    return {"dimensions": dimensions, "series": series}


def param_importance_rows(product: dict[str, Any], aggregation: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    params = active_params(product, plan_type)
    driver_counts = Counter()
    for row in aggregation.get("top_purchase_drivers") or []:
        if isinstance(row, dict):
            driver_counts[str(row.get("item") or "")] = int(row.get("count") or 0)
    max_driver = max(driver_counts.values() or [1])
    result: list[dict[str, Any]] = []
    for item in params:
        name = str(item["name"])
        driver_bonus = 0
        for driver, count in driver_counts.items():
            if name and name in driver:
                driver_bonus = max(driver_bonus, count)
        weight = safe_float(item.get("weight"), 3.0)
        contribution = clamp(weight / 5 * 70 + driver_bonus / max_driver * 25, 20, 100)
        result.append({**item, "importance": round(contribution, 1), "weight": round(weight, 2)})
    return result


def strategy_rows(market: dict[str, Any], aggregation: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    intent = safe_float(aggregation.get("purchase_intent_avg"), 0.5)
    evidence_quality = aggregation.get("evidence_quality") if isinstance(aggregation.get("evidence_quality"), dict) else {}
    coverage = safe_float(evidence_quality.get("price_coverage_pct"), 0.0) / 100
    raw = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    if raw:
        rows = raw[:1] if plan_type == "basic" else raw[:3]
        result = []
        for index, item in enumerate(rows, 1):
            if isinstance(item, dict):
                name = item.get("name") or f"策略{index}"
                intensity = safe_float(item.get("intensity"), 55)
                discount = safe_float(item.get("price_discount"), 0)
            elif isinstance(item, str) and item.strip():
                name = item.strip()
                intensity = 55
                discount = 0
            else:
                continue
            reach = round(clamp(45 + intensity * 0.45, 25, 95), 1)
            conversion_lift = round(clamp(intent * 70 + discount * 0.18, 5, 85), 1)
            cost_pressure = round(clamp(intensity * 0.35 + discount * 0.25, 5, 70), 1)
            risk_penalty = round(clamp((1 - coverage) * 18, 0, 30), 1)
            roi = 0.8 + intent * 1.6 + reach / 100 * 0.45 + conversion_lift / 100 * 0.55 - cost_pressure / 100 * 0.3 - risk_penalty / 100
            result.append(
                {
                    "name": name,
                    "roi": round(roi, 2),
                    "intensity": intensity,
                    "discount": discount,
                    "reach_score": reach,
                    "conversion_lift": conversion_lift,
                    "cost_pressure": cost_pressure,
                    "risk_penalty": risk_penalty,
                }
            )
        if result:
            return result
    name = market.get("strategy") or market.get("basic_selected_strategy") or "标准策略"
    reach = 60 if plan_type == "pro" else 45
    conversion_lift = round(clamp(intent * 75, 5, 85), 1)
    cost_pressure = 28 if plan_type == "pro" else 18
    risk_penalty = round(clamp((1 - coverage) * 18, 0, 30), 1)
    roi = 0.9 + intent * 1.55 + reach / 100 * 0.45 + conversion_lift / 100 * 0.45 - cost_pressure / 100 * 0.25 - risk_penalty / 100
    return [
        {
            "name": str(name),
            "roi": round(roi, 2),
            "intensity": 50,
            "discount": 0,
            "reach_score": reach,
            "conversion_lift": conversion_lift,
            "cost_pressure": cost_pressure,
            "risk_penalty": risk_penalty,
        }
    ]


def channel_effect_rows(market: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    channels: list[str] = []
    strategies = market.get("strategies") if isinstance(market.get("strategies"), list) else []
    for strategy in strategies:
        if isinstance(strategy, dict) and isinstance(strategy.get("channels"), list):
            channels.extend(str(item) for item in strategy["channels"])
    if not channels:
        channels = ["社交媒体", "电商平台", "KOL合作"] if plan_type == "pro" else ["标准渠道"]
    counts = Counter(channels)
    rows = [{"name": name, "seed": count} for name, count in counts.items()]
    return normalize_percent(rows)


def price_sensitivity_rows(product: dict[str, Any], aggregation: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    price = product_price(product) or 399.0
    multipliers = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3] if plan_type == "pro" else [0.85, 0.95, 1.0, 1.05, 1.15]
    base = clamp(safe_float(aggregation.get("purchase_intent_avg"), 0.5) * 100, 5, 95)
    price_acceptance = aggregation.get("price_sensitivity_summary") if isinstance(aggregation.get("price_sensitivity_summary"), dict) else {}
    elasticity = 1.0
    high = price_acceptance.get("high") if isinstance(price_acceptance.get("high"), dict) else {}
    if safe_float(high.get("count"), 0) > 0:
        elasticity += 0.25
    rows = []
    for multiplier in multipliers:
        delta = (1 - multiplier) * 80 * elasticity
        intent = round(clamp(base + delta, 3, 98), 1)
        rows.append(
            {
                "price": round(price * multiplier, 2),
                "multiplier": round(multiplier, 2),
                "intent": intent,
                "elasticity": round(elasticity, 2),
                "note": "推荐价格带" if 55 <= intent <= 85 and 0.9 <= multiplier <= 1.1 else "",
            }
        )
    return rows


def purchase_intent_distribution_rows(aggregation: dict[str, Any]) -> list[dict[str, Any]]:
    distribution = aggregation.get("purchase_intent_distribution") if isinstance(aggregation.get("purchase_intent_distribution"), dict) else {}
    label_map = {"buy": "愿意购买", "consider": "考虑购买", "not_buy": "暂不购买"}
    return [
        {"name": label_map.get(str(key), str(key)), "count": int(value or 0)}
        for key, value in distribution.items()
    ]


def top_factor_rows(aggregation: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = aggregation.get(key) if isinstance(aggregation.get(key), list) else []
    return [
        {"name": str(item.get("item") or "未命名因素"), "count": int(item.get("count") or 0)}
        for item in rows
        if isinstance(item, dict)
    ]


def recommended_price_band(price_rows: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in price_rows if 55 <= safe_float(row.get("intent"), 0) <= 85]
    if not viable:
        viable = price_rows
    prices = [safe_float(row.get("price"), 0) for row in viable]
    intents = [safe_float(row.get("intent"), 0) for row in price_rows]
    return {
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "peak_intent": round(max(intents), 1) if intents else None,
        "analysis": "价格敏感曲线用于判断价格上下浮动对购买意愿的方向性影响，正式定价仍需结合成本与渠道数据。",
    }


def sensitivity_waterfall_rows(param_rows: list[dict[str, Any]], aggregation: dict[str, Any]) -> list[dict[str, Any]]:
    base = round(clamp(safe_float(aggregation.get("purchase_intent_avg"), 0.5) * 100, 5, 95), 1)
    rows = [{"name": "当前基线", "delta": 0, "value": base}]
    for item in param_rows[:6]:
        delta = round((safe_float(item.get("importance"), 50) - 50) / 10, 1)
        rows.append({"name": f"{item.get('name')}优化", "delta": delta, "value": round(clamp(base + delta, 0, 100), 1)})
    return rows


def target_match_label(intent_index: float) -> str:
    if intent_index >= 75:
        return "高度匹配"
    if intent_index >= 55:
        return "中度匹配"
    return "低度匹配"


def social_evolution_rows(aggregation: dict[str, Any], plan_type: str) -> list[dict[str, Any]]:
    summaries = aggregation.get("social_evolution") if isinstance(aggregation.get("social_evolution"), list) else []
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        round_number = int(summary.get("round") or len(rows) + 1)
        rows.append(
            {
                "round": round_number,
                "name": "整体人群",
                "value": round(safe_float(summary.get("overall_purchase_intent")) * 100, 1),
                "social_influence": round(safe_float(summary.get("social_influence_avg")) * 100, 1),
                "max_score_change": round(safe_float(summary.get("max_score_change")) * 100, 1),
            }
        )
        if plan_type != "pro":
            continue
        segments = summary.get("segment_evolution") if isinstance(summary.get("segment_evolution"), list) else []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            rows.append(
                {
                    "round": round_number,
                    "name": str(segment.get("name") or "目标人群"),
                    "value": round(safe_float(segment.get("value")), 1),
                    "ratio": round(safe_float(segment.get("ratio")), 1),
                    "count": int(segment.get("count") or 0),
                }
            )
    return rows


def build_chart_data(
    snapshot: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    agents: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    aggregation: dict[str, Any],
    plan_type: str = "basic",
) -> dict[str, Any]:
    plan_type = "pro" if plan_type == "pro" else "basic"
    product = snapshot.get("product_definition") or {}
    market = snapshot.get("market_config") or {}
    competitors = collect_competitors(snapshot, evidence, plan_type)
    market_share_full = market_share_rows(product, competitors, aggregation)
    market_share = compact_market_share_rows(market_share_full)
    param_importance = param_importance_rows(product, aggregation, plan_type)
    price_sensitivity = price_sensitivity_rows(product, aggregation, plan_type)
    intent_index = round(clamp(safe_float(aggregation.get("purchase_intent_avg"), 0.0) * 100, 0, 100), 1)
    self_share = next((row["share"] for row in market_share if row.get("role") == "self"), 0)
    chart_data = {
        "prompt_version": PROMPT_VERSION,
        "plan_type": plan_type,
        "overview_metrics": {
            "purchase_intent_index": intent_index,
            "estimated_market_share": self_share,
            "target_match": target_match_label(intent_index),
            "evidence_count": sum(len(items) for items in evidence.values()),
            "competitor_count": len(competitors),
            "agent_count": len(agents),
            "decision_count": len(decisions),
            "confidence_score": aggregation.get("confidence", {}).get("score")
            if isinstance(aggregation.get("confidence"), dict)
            else None,
            "confidence_level": aggregation.get("confidence", {}).get("label")
            if isinstance(aggregation.get("confidence"), dict)
            else None,
        },
        "purchase_intent_by_segment": purchase_intent_rows(aggregation, plan_type),
        "purchase_intent_distribution": purchase_intent_distribution_rows(aggregation),
        "purchase_drivers": top_factor_rows(aggregation, "top_purchase_drivers"),
        "purchase_blockers": top_factor_rows(aggregation, "top_purchase_blockers"),
        "market_share": market_share,
        "market_share_full": market_share_full,
        "competitor_analysis": competitor_analysis_rows(competitors, market_share_full),
        "param_importance": param_importance,
        "strategy_roi": strategy_rows(market, aggregation, plan_type),
        "channel_effect": channel_effect_rows(market, plan_type),
        "price_sensitivity": price_sensitivity,
        "recommended_price_band": recommended_price_band(price_sensitivity),
        "social_evolution": social_evolution_rows(aggregation, plan_type),
        "social_rounds": aggregation.get("social_evolution") if isinstance(aggregation.get("social_evolution"), list) else [],
    }
    if plan_type == "pro":
        competitor_radar_full = competitor_radar_rows(product, competitors, aggregation)
        chart_data["competitor_radar"] = compact_competitor_radar(competitor_radar_full)
        chart_data["competitor_radar_full"] = competitor_radar_full
        chart_data["sensitivity_waterfall"] = sensitivity_waterfall_rows(param_importance, aggregation)
    return chart_data
